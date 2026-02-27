-- Script de inicialização da base de dados MySQL
-- Executado automaticamente quando o container é criado

-- Configurar timezone
SET GLOBAL time_zone = '+01:00';
SET time_zone = '+01:00';

-- Configurar charset
ALTER DATABASE leguas_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- Criar utilizador se não existir (backup)
CREATE USER IF NOT EXISTS 'leguas_user'@'%' IDENTIFIED BY 'leguas_password_dev';
GRANT ALL PRIVILEGES ON leguas_db.* TO 'leguas_user'@'%';
FLUSH PRIVILEGES;

SELECT 'Base de dados inicializada com sucesso!' AS status;
