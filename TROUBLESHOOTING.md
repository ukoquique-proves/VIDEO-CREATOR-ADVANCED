# Troubleshooting



## Picsum images don't match my prompts

**Symptom:** When `use_picsum: true` is set in the configuration, the generated images are high-quality and consistent across runs, but they have nothing to do with the text prompts provided (e.g., a prompt for "a futuristic city" returns a photo of a mountain).

**Cause:** The Picsum seed endpoint (`picsum.photos/seed/{seed}/...`) is deterministic but not semantic. Using a keyword-derived seed (like `futuristic-city`) ensures that the same prompt always results in the same image, but Picsum does not analyze the keyword to find a matching photo. It simply assigns a random photo from its library to that specific seed string.

**Fix:** This is intended behavior for the fast, offline-friendly placeholder mode. For actual AI-generated images that match your prompts, ensure that:
1. `use_picsum` is set to `false` in your config.
2. You have a working AI image provider configured (like Pollinations or HuggingFace) via Lingo_PERSONAS.

