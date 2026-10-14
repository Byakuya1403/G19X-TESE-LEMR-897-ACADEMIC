-- Actualización aditiva v0.9: ejecutar en la base finanzas ya existente.
-- La aplicación también crea estas dos tablas al arrancar.
-- No renombra usuarios ni altera los datos financieros.
BEGIN;
CREATE TABLE IF NOT EXISTS user_emails (
	user_id INTEGER NOT NULL, 
	email VARCHAR(254) NOT NULL, 
	verified BOOLEAN NOT NULL, 
	PRIMARY KEY (user_id), 
	FOREIGN KEY(user_id) REFERENCES users (id), 
	UNIQUE (email)
);
CREATE TABLE IF NOT EXISTS user_invitations (
	user_id INTEGER NOT NULL, 
	token_hash VARCHAR(64) NOT NULL, 
	expires FLOAT NOT NULL, 
	PRIMARY KEY (user_id), 
	FOREIGN KEY(user_id) REFERENCES users (id), 
	UNIQUE (token_hash)
);
COMMIT;
