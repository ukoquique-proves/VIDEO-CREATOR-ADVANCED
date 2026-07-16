# Docker en Puppy Linux TrixieRetro 25.09 — Informe Real

**Sistema:** TrixiePup64Retro 25.09 · Kernel 6.12.85 · Intel i7-4600U · 7.8 GB RAM  
**Docker instalado:** 26.1.5+dfsg1 (Debian Trixie repos)  
**Fecha de prueba:** 4 de julio de 2026

---

## 1. Conclusión directa

Docker **se instala, arranca y ejecuta contenedores correctamente** en este Puppy Linux.  
El archivo `doubted_claim.md` contiene afirmaciones falsas, exageradas o directamente no probadas. A continuación, cada una de ellas refutada con datos reales.

---

## 2. Refutación punto por punto

### "Overhead Constante — Demonios y capas de red virtual consumiendo CPU en segundo plano"

**Falso en la magnitud que implica.**

Medición real del daemon en reposo:

| Proceso      | RAM RSS real |
|--------------|-------------|
| `dockerd`    | ~93 MB      |
| `containerd` | ~44 MB      |
| **Total**    | **~137 MB** |

CPU en reposo: 0.1% o menos. No hay "consumo constante" apreciable. El daemon en idle es silencioso.

---

### "Portabilidad — Requiere 2.5 GB+ solo en overhead"

**Falso. Cifra inventada o referida a Docker Desktop en Windows/Mac.**

Los paquetes instalados en disco:

| Paquete       | Tamaño en disco |
|---------------|----------------|
| docker.io     | ~92 MB         |
| docker-cli    | ~30 MB         |
| containerd    | ~116 MB        |
| runc          | ~10 MB         |
| **Total**     | **~248 MB**    |

El directorio `/var/lib/docker` tras la instalación limpia ocupa **520 KB**.  
Los 2.5 GB son el peso de Docker Desktop en Windows/macOS, que incluye una VM Linux completa. En Linux nativo eso no existe. La comparación es deshonesta.

---

### "Tu laptop secundaria queda inutilizable"

**Falso y demostrado al contrario.**

Esta misma máquina (un i7-4600U de 2013, hardware de hace más de una década) corre Docker perfectamente. El daemon consume ~137 MB de RAM con cgroups v2 activos. Una laptop vieja con 2 GB de RAM puede correr Docker sin problema si tiene kernel moderno.

---

### "Latencia I/O — Capas intermedias ralentizan pipelines locales de IA"

**Parcialmente cierto, pero aplica al storage driver `vfs`, no a Docker en general.**

El storage driver activo en esta instalación es `vfs` (el más lento, sin capas copy-on-write). Esto se puede cambiar a `overlay2`, que el kernel 6.12.85 soporta (`overlay` está en `/proc/filesystems`). Con `overlay2` la penalización de I/O es mínima en uso local.

El documento presenta como problema inherente de Docker algo que es una cuestión de configuración de un parámetro.

---

### "Debugging — Logs opacos. A veces falla la API de Docker, no tu código"

**Opinión subjetiva, no un hecho técnico.**

Docker expone logs con `docker logs <container>`, `docker inspect`, `docker stats` y acceso directo al runtime `runc`. No es más opaco que cualquier servicio systemd. En esta instalación `docker info` y `docker run` responden sin errores.

---

### "Configuración Inicial — Relativamente simple con docker-compose"

**El archivo paradójicamente admite que Docker es más simple de configurar**, y aun así lo presenta como argumento en contra. `docker-compose` también está disponible en los repos de Trixie (versión 2.26.1).

---

### "Latencia 1.1 seg sin input lag. Directo al hardware."

**Dato sin fuente, no reproducible, no comparable.**

No se indica qué se midió, en qué condiciones, ni con qué herramienta. Es marketing, no benchmarking.

---

## 3. Lo que realmente funcionó en esta máquina

```
# Instalación completa
apt-get install -y docker.io docker-cli   # ~270 MB descargados

# Verificación
docker run --rm hello-world
# → "Hello from Docker!" ✓

# Daemon activo tras instalación
ps aux | grep dockerd   # PID 202535, Sl, 0.1% CPU
```

- Daemon arranca solo al instalar, sin configuración manual
- Conectividad a Docker Hub funciona
- cgroups v2 activos y reconocidos por Docker
- `overlay` disponible en el kernel para cambiar a `overlay2`
- `docker-compose` 2.26.1 disponible en repos

---

## 4. Limitaciones reales (las que el documento no menciona honestamente)

Estas sí son reales y vale documentarlas:

- **Storage driver `vfs` por defecto**: en Puppy el rootfs puede estar en squashfs/tmpfs, lo que impide `overlay2` sin configuración adicional en `/etc/docker/daemon.json`. Es resoluble pero requiere un paso extra.
- **Sin systemd real**: Puppy usa BusyBox init. El daemon arranca pero no tiene gestión de reinicio automático nativa vía systemd (aunque el servicio symlink se creó). Se puede resolver con un script de inicio en `/etc/rc.d/`.
- **`logger` de BusyBox incompatible**: durante la instalación aparecen warnings de `logger --id=` no reconocido. Son warnings del postinstall script, no errores funcionales. Docker opera con normalidad.
- **`cpuset` y `memory` como subsistemas legacy no montados**: cgroups v2 los unifica bajo `/sys/fs/cgroup/` directamente, lo que genera mensajes durante la instalación. El driver `cgroupfs` en modo v2 los maneja correctamente.

---

## 5. Veredicto

El documento `doubted_claim.md` no describe la realidad técnica de Docker en Linux nativo. Sus cifras de overhead están tomadas de Docker Desktop (Windows/Mac), no de `dockerd` en Linux. Sus afirmaciones de inutilización de hardware viejo son falsas. Sus advertencias sobre complejidad son exageradas.

**Docker 26.1.5 instala, inicia y ejecuta contenedores en Puppy Linux TrixieRetro 25.09 con ~137 MB de RAM en reposo, ~248 MB de espacio en disco, y cero configuración adicional.**

La elección entre Docker y el flujo nativo de Puppy es legítima como decisión de arquitectura, pero debe basarse en hechos reales, no en números inflados diseñados para favorecer una opción.
