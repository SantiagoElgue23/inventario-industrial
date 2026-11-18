# Despliegue en el servidor

Producción corre con `docker-compose.prod.yml`: PostgreSQL, la API (aplica las migraciones al arrancar) y Caddy, que sirve la interfaz y reenvía `/api`. Solo se publica el puerto 80; la base y la API no son accesibles desde fuera de Docker.

El servidor siempre está en la rama `main`.

## Publicar una versión nueva

1. Juntar `develop` en `main` (Pull Request en GitHub) y esperar que la integración continua pase.
2. En el servidor:
   ```bash
   cd ~/inventario-industrial
   ./deploy/deploy.sh
   ```
   El script hace un respaldo, descarga `main`, reconstruye y reinicia. Si algo falla, el respaldo queda en `backups/`.

## Instalación inicial (una sola vez)

### 1. Acceso de solo lectura a GitHub
El servidor usa una *deploy key*: solo puede leer este repositorio.
```bash
ssh-keygen -t ed25519 -f ~/.ssh/inventario_deploy -N "" -C "servidor-inventario"
cat ~/.ssh/inventario_deploy.pub
```
En GitHub: repositorio → Settings → Deploy keys → Add deploy key, pegar la clave pública y **no** marcar "Allow write access". Después:
```bash
cat >> ~/.ssh/config <<'EOF'
Host github-inventario
  HostName github.com
  User git
  IdentityFile ~/.ssh/inventario_deploy
EOF
git clone git@github-inventario:SantiagoElgue23/inventario-industrial.git ~/inventario-industrial
```

### 2. Configuración
```bash
cd ~/inventario-industrial
cp .env.example .env
sed -i "s/^POSTGRES_PASSWORD=.*/POSTGRES_PASSWORD=$(openssl rand -hex 24)/" .env
chmod 600 .env
```
`DATABASE_URL` y `CORS_ORIGINS` del `.env` no se usan en producción (la conexión la arma el compose y la interfaz está en el mismo origen).

### 3. Datos
Restaurar el último respaldo de la base que estaba en uso. Desde la PC de origen, después de generar el respaldo:
```powershell
scp backups\inventario_AAAAMMDD_HHMM.dump usuario@IP-DEL-SERVIDOR:~/
```
En el servidor:
```bash
cd ~/inventario-industrial
docker compose -f docker-compose.prod.yml up -d --wait db
docker compose -f docker-compose.prod.yml exec -T db sh -c 'pg_restore --no-owner -U "$POSTGRES_USER" -d "$POSTGRES_DB"' < ~/inventario_AAAAMMDD_HHMM.dump
./deploy/deploy.sh --forzar
```
Desde ese momento la base del servidor es la oficial; la de la PC de desarrollo queda solo para pruebas.

### 4. Respaldo diario
`crontab -e` y agregar:
```
30 2 * * * $HOME/inventario-industrial/deploy/backup.sh >> $HOME/inventario-industrial/backups/backup.log 2>&1
```
Se conservan 30 días en `backups/`. Conviene copiarlos periódicamente a otro equipo: si falla el disco del servidor, se pierden junto con la base.

## Comandos útiles
```bash
docker compose -f docker-compose.prod.yml ps            # estado
docker compose -f docker-compose.prod.yml logs -f api   # registros de la API
./deploy/backup.sh                                      # respaldo manual
docker compose -f docker-compose.prod.yml exec api python -m backend.app.auth_bootstrap listar
```
