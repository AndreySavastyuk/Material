"""
Безопасная версия метода validate_session с интегрированными проверками безопасности.
"""

def validate_session_secure(self, session_token: str, ip_address: str = None, 
                           user_agent: str = None) -> Optional[Dict[str, Any]]:
    """
    Проверяет валидность токена сессии с дополнительными проверками безопасности.
    
    Args:
        session_token: Токен сессии
        ip_address: IP-адрес для проверки
        user_agent: User Agent для проверки
        
    Returns:
        Данные сессии если токен валиден, None если не валиден
    """
    try:
        # 1. Базовая проверка токена в БД
        cursor = self.db.conn.cursor()
        cursor.execute("""
            SELECT s.*, u.login, u.name 
            FROM user_sessions s
            JOIN users u ON s.user_id = u.id
            WHERE s.session_token = ? AND s.is_active = 1
        """, (session_token,))
        
        session = cursor.fetchone()
        
        if not session:
            self._log_session_action(
                action='invalid_token',
                session_token=session_token,
                ip_address=ip_address,
                success=False,
                reason="Token not found or inactive"
            )
            return None
        
        session_dict = dict(session)
        user_id = session_dict['user_id']
        user_login = session_dict['login']
        
        # 2. Проверяем истечение времени
        expires_at = datetime.fromisoformat(session_dict['expires_at'])
        if expires_at <= datetime.now():
            self._invalidate_session_by_id(
                session_dict['id'], 
                reason="Session expired"
            )
            
            self._log_session_action(
                user_id=user_id,
                action='session_expired',
                session_token=session_token,
                ip_address=ip_address,
                success=False,
                reason="Session expired"
            )
            return None
        
        # 3. Проверяем brute force защиту для IP
        if ip_address and not self._security_manager.check_brute_force_protection(ip_address):
            self._log_session_action(
                user_id=user_id,
                action='ip_blocked',
                session_token=session_token,
                ip_address=ip_address,
                success=False,
                reason="IP temporarily blocked due to brute force protection"
            )
            return None
        
        # 4. Проверяем на угон сессии
        if ip_address and user_agent:
            if self._security_manager.detect_session_hijacking(
                session_token, ip_address, user_agent
            ):
                # Инвалидируем сессию при подозрении на угон
                self._invalidate_session_by_id(
                    session_dict['id'], 
                    reason="Suspected session hijacking"
                )
                
                self._log_session_action(
                    user_id=user_id,
                    action='hijacking_detected',
                    session_token=session_token,
                    ip_address=ip_address,
                    success=False,
                    reason="Session hijacking detected and blocked"
                )
                
                # Инвалидируем все сессии пользователя для безопасности
                self.invalidate_all_user_sessions(user_id, "Security: session hijacking detected")
                
                logger.warning(f"Обнаружен угон сессии для пользователя {user_login}")
                return None
        
        # 5. Проверяем ротацию токена
        rotated_token = self._security_manager.rotate_session_token(
            session_token, user_id, ip_address
        )
        
        if rotated_token and rotated_token != session_token:
            # Токен был ротирован, обновляем данные сессии
            session_dict['session_token'] = rotated_token
            
            self._log_session_action(
                user_id=user_id,
                action='token_rotated',
                session_token=rotated_token,
                ip_address=ip_address,
                success=True,
                reason="Scheduled token rotation"
            )
        
        # 6. Проверяем стандартное изменение IP если включено
        if (self._get_setting('track_ip_changes', 'true').lower() == 'true' and 
            ip_address and session_dict['ip_address'] and 
            ip_address != session_dict['ip_address']):
            
            logger.info(f"IP changed for session {session_dict['id']}: "
                       f"{session_dict['ip_address']} -> {ip_address}")
            
            if self._get_setting('invalidate_on_ip_change', 'false').lower() == 'true':
                self._invalidate_session_by_id(
                    session_dict['id'], 
                    reason="IP address changed"
                )
                
                self._log_session_action(
                    user_id=user_id,
                    action='session_ip_changed',
                    session_token=session_token,
                    ip_address=ip_address,
                    success=False,
                    reason=f"IP changed from {session_dict['ip_address']} to {ip_address}"
                )
                return None
        
        # 7. Применяем лимиты сессий
        invalidated_tokens = self._security_manager.enforce_session_limits(user_id)
        if session_token in invalidated_tokens:
            self._log_session_action(
                user_id=user_id,
                action='session_limit_exceeded',
                session_token=session_token,
                ip_address=ip_address,
                success=False,
                reason="Session limit exceeded, old session invalidated"
            )
            return None
        
        # 8. Обновляем время последней активности
        self._update_session_activity(session_dict['id'], ip_address)
        
        # 9. Логируем успешную валидацию
        self._log_session_action(
            user_id=user_id,
            action='session_validated',
            session_token=session_dict.get('session_token', session_token),
            ip_address=ip_address,
            success=True,
            reason="Session successfully validated"
        )
        
        return session_dict
        
    except Exception as e:
        logger.error(f"Ошибка валидации сессии {session_token}: {e}")
        
        # Логируем ошибку
        self._log_session_action(
            action='validation_error',
            session_token=session_token,
            ip_address=ip_address,
            success=False,
            reason=f"Validation error: {str(e)}"
        )
        
        return None


def create_session_secure(self, user_id: int, remember_me: bool = False, 
                         ip_address: str = None, user_agent: str = None) -> Dict[str, Any]:
    """
    Создает новую сессию с дополнительными проверками безопасности.
    
    Args:
        user_id: ID пользователя
        remember_me: Флаг "Запомнить меня"
        ip_address: IP-адрес пользователя
        user_agent: Информация о браузере/приложении
        
    Returns:
        Словарь с данными сессии
        
    Raises:
        SecurityError: При нарушении правил безопасности
        BusinessLogicError: При ошибке создания сессии
    """
    try:
        # 1. Проверяем brute force защиту
        if ip_address and not self._security_manager.check_brute_force_protection(ip_address):
            raise SecurityError(
                message="IP адрес временно заблокирован",
                details={'ip_address': ip_address}
            )
        
        # 2. Применяем лимиты сессий заранее
        invalidated_tokens = self._security_manager.enforce_session_limits(user_id)
        if invalidated_tokens:
            logger.info(f"Инвалидированы {len(invalidated_tokens)} старых сессий для пользователя {user_id}")
        
        # 3. Создаем безопасный токен
        secure_token_data = self._security_manager.create_secure_token(
            user_id, ip_address, user_agent
        )
        session_token = secure_token_data['token']
        
        # 4. Вычисляем время истечения
        timeout_seconds = self._get_session_timeout(remember_me)
        now = datetime.now()
        expires_at = now + timedelta(seconds=timeout_seconds)
        
        # 5. Получаем информацию о системе если user_agent не передан
        if not user_agent:
            system_info = self._get_user_agent_info()
            user_agent = json.dumps(system_info)
        
        # 6. Создаем запись сессии
        cursor = self.db.conn.cursor()
        cursor.execute("""
            INSERT INTO user_sessions 
            (user_id, session_token, created_at, last_activity, expires_at, 
             remember_me, ip_address, user_agent, is_active)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)
        """, (
            user_id, session_token, now.isoformat(), now.isoformat(),
            expires_at.isoformat(), remember_me, ip_address, user_agent
        ))
        
        session_id = cursor.lastrowid
        self.db.conn.commit()
        
        # 7. Сбрасываем счетчик неудачных попыток при успешном создании сессии
        if ip_address:
            self._security_manager.reset_failed_attempts(ip_address=ip_address)
        
        # 8. Логируем создание сессии
        self._log_session_action(
            user_id=user_id,
            action='secure_session_created',
            session_token=session_token,
            ip_address=ip_address,
            user_agent=user_agent,
            success=True,
            reason=f"Secure session created: remember_me={remember_me}, expires={expires_at.isoformat()}"
        )
        
        logger.info(f"Создана безопасная сессия {session_id} для пользователя {user_id}")
        
        return {
            'session_id': session_id,
            'session_token': session_token,
            'user_id': user_id,
            'created_at': now.isoformat(),
            'expires_at': expires_at.isoformat(),
            'remember_me': remember_me,
            'is_active': True,
            'security_features': {
                'signed_token': True,
                'brute_force_protection': True,
                'hijacking_detection': True,
                'automatic_rotation': True
            }
        }
        
    except SecurityError:
        # Записываем неудачную попытку для brute force защиты
        if ip_address:
            self._security_manager.record_failed_attempt(ip_address)
        raise
    
    except Exception as e:
        self.db.conn.rollback()
        logger.error(f"Ошибка создания безопасной сессии для пользователя {user_id}: {e}")
        
        # Записываем неудачную попытку
        if ip_address:
            self._security_manager.record_failed_attempt(ip_address)
        
        # Логируем неудачную попытку
        self._log_session_action(
            user_id=user_id,
            action='secure_session_create_failed',
            ip_address=ip_address,
            user_agent=user_agent,
            success=False,
            reason=str(e)
        )
        
        raise BusinessLogicError(
            message="Не удалось создать безопасную сессию",
            original_error=e,
            suggestions=["Проверьте подключение к базе данных", "Попробуйте войти снова"]
        ) 