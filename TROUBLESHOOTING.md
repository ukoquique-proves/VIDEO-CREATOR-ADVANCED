# Troubleshooting

## Image generation hangs on cloud infrastructure (AWS / VPS)

### Síntomas

El pipeline se queda bloqueado en la fase de generación de imágenes, con el último log repitiendo:

```
INFO  src.image_providers.manager: [1/9] Generating: ...
INFO  src.image_providers.manager: Trying provider 1/3: pollinations...
```

...durante varios minutos sin avanzar, o bien:

```
WARNING src.image_providers.manager: pollinations timed out after 120.0s — trying next provider.
```

### Causa raíz

El problema tiene dos capas:

**1. Pollinations bloqueado por detección de cloud (seguridad prevista)**

`src/image_providers/cloud_detection.py` detecta la IP de la máquina y, en infraestructuras donde Pollinations suele bloquear cloud IPs, lo marca como proveedor baneado. El registro `CLOUD_PROVIDER_BANS` actualmente contiene:

- `CloudProvider.AWS: ["pollinations"]`
- `CloudProvider.DIGITALOCEAN: ["pollinations"]`
- `CloudProvider.HETZNER: ["pollinations"]`

Esto evita intentar una petición que probablemente fallará por IP-block y permite el cambio inmediato a otro proveedor.

Si ese registro se vacía accidentalmente, esta protección queda desactivada y la aplicación vuelve a intentar proveedores bloqueados.

**2. Lentitud variable de proveedores externos**

Tanto Cloudflare Workers AI como Pollinations pueden tardar entre 10 y 120+ segundos por imagen dependiendo de la carga del servicio en ese momento. Cuando el proveedor primario (Cloudflare) está lento, el pipeline esperaba el timeout completo antes de hacer fallback. Con resoluciones altas (1920×1080) y prompts complejos, esto se multiplica por cada imagen del batch.

El manager ahora envuelve cada llamada en un `ThreadPoolExecutor` con `per_image_timeout=120s`, lo que hace que el fallback se intente tan pronto como el timeout expire. Sin embargo, dado que Python no puede forzar la terminación de hilos en ejecución, los subprocesos bloqueados pueden seguir vivos en segundo plano; por eso es importante que los proveedores también establezcan límites de tiempo de socket y petición en su propia lógica.

**3. Lock de proceso huérfano**

Cuando el proceso se interrumpe (Ctrl+C, kill, o error fatal), el archivo `.generation.lock` puede quedar sin eliminarse. En el siguiente intento, `main.py` lee el PID del lock, verifica si el proceso sigue vivo, y si el PID fue reasignado a otro proceso del sistema, bloquea la ejecución con:

```
ERROR A video generation is already running for output directory ...
```

### Solución manual

Si el pipeline no arranca y aparece el error de lock, eliminar el archivo manualmente:

```bash
rm -f output/logs/.generation.lock
```

### Configuración recomendada para entornos cloud

Para evitar depender de Cloudflare cuando está lento, forzar Pollinations directamente en el config:

```yaml
image_engine: "pollinations"
```

Esto mueve a Pollinations al primer lugar de la lista de proveedores y evita el timeout de 120s de Cloudflare antes del fallback.

### Workaround si ambos proveedores están lentos

Si ni Cloudflare ni Pollinations responden en tiempo razonable, la alternativa es proporcionar las imágenes localmente:

```yaml
visual_assets:
  asset_type: "image_sequence"
  images:
    - "assets/my_scene_01.jpg"
    - "assets/my_scene_02.jpg"
```

Esto elimina completamente la dependencia de proveedores externos de imagen.
