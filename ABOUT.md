Este proyecto, VideoCreation , es una plataforma configurable para la generación automática de videos a partir de texto (speech), imágenes o prompts de IA. Está diseñado siguiendo una arquitectura de adaptadores que permite intercambiar proveedores de servicios (TTS, generación de imágenes, ensamblado de video) de manera sencilla.

A continuación, presento un resumen detallado de los componentes clave y el flujo de trabajo:

### Arquitectura General
El corazón del sistema es el orchestrator.py , que coordina un pipeline de 4 pasos delegando cada tarea a adaptadores especializados:

1. TTS (Audio) : Convierte el texto en voz.
2. Visuals (Imágenes) : Prepara las imágenes (ya sean archivos locales o generadas por IA).
3. Subtitles : (Opcional) Genera los tiempos de los subtítulos basándose en el audio.
4. Assembly : Une el audio, las imágenes y los subtítulos en el archivo de video final.

> ⚠️ **Image Modification Not Supported**: `image_modification_instructions` is reserved for future use and is **intentionally not implemented in this version**. The schema validates and rejects any attempts to use this field with a clear error message. Do not include this field in your configuration — it will cause validation to fail.

### Componentes Principales
- schema.py : Define los modelos de datos (usando Pydantic) para la configuración del video, incluyendo el título, contenido del habla, activos visuales, orientación (vertical/horizontal) y proveedores.
- orchestrator.py : La clase VideoOrchestrator gestiona el ciclo de vida de la creación del video y el manejo de directorios de trabajo (workspaces).
- tts_adapter.py : Utiliza principalmente Kokoro para generar audio de alta calidad de forma local y gratuita, con soporte para múltiples idiomas; incluye edge-tts y otros fallbacks cuando Kokoro no está disponible.
- image_adapter.py : Implementa una estrategia de "fallback" para imágenes:
  - Utiliza proveedores nativos (Cloudflare, SiliconFlow, Pollinations, HF).
  - Picsum se usa solo cuando `engine="picsum"` se solicita explícitamente.
  - Finalmente, crea placeholders con Pillow si ningún proveedor nativo está disponible.
- subtitle_renderer.py : Un componente especializado que quema (burn-in) subtítulos en el video usando ffmpeg/ASS para mayor precisión. El renderizado de muestra con Pillow se mantiene solo como helper de pruebas, no como flujo de producción.
- assembler_adapter.py : Utiliza un backend nativo de MoviePy para ensamblar el video, con una implementación local totalmente desacoplada.
### Interfaces de Usuario
El proyecto ofrece dos formas principales de interacción:

1. CLI : A través de main.py , permitiendo ejecutar configuraciones desde archivos YAML o JSON.
2. UI Web : Una interfaz interactiva construida con Streamlit en ui.py , que permite configurar el video, ver logs en tiempo real y previsualizar el resultado final.

### Estado de Pruebas
Cuenta con una suite de pruebas robusta en la carpeta tests/ , que utiliza mocks para simular los servicios externos (IA, TTS), permitiendo validar la lógica de orquestación y renderizado de forma rápida y offline.