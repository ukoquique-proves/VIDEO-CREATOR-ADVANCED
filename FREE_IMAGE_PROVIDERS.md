These notes are aspirational: `unsplash`, `pexels`, and `pixabay` are not currently implemented in the native provider library.

At the moment, the supported image engines are:

If you configure `image_engine: "unsplash"` or `image_engine: "pexels"`, the application will reject it because those providers are not yet wired into the codebase.

## Free Image Providers — Status

Status: The native provider library currently supports the following image engines:

- `cloudflare`
- `siliconflow`
- `pollinations`
- `huggingface`
- `picsum`

Planned (not implemented): `unsplash`, `pexels`, and `pixabay` are documented here for convenience but are not wired into the codebase. Do not set `image_engine` to these values; `src/image_adapter.py` explicitly rejects them and the registry will not instantiate them.

If you want to add one of these providers, the implementation approach is straightforward: use the provider's search API to find a relevant photo for each prompt (extract keywords, query, pick top result), implement an `ImageProvider` subclass under `src/image_providers/`, register a `ProviderSpec` in `src/image_providers/registry.py`, and add the env var(s) to `.env`.

Quick links (for implementers):

- Unsplash: https://unsplash.com/developers (Access Key shown after registering an app)
- Pexels: https://www.pexels.com/api (API key shown after creating an account)
- Pixabay: https://pixabay.com/api/docs (API key shown when logged in)

Unsplash API — keyword search, returns topically relevant photos, free with a registered app (takes 2 minutes to get a key at unsplash.com/developers)
Pixabay API — same idea, free key, no approval wait
Pexels API — same, free key
All three work identically: extract keywords from each prompt, fire a search query, pick the top result. The implementation would be nearly identical to what we built for Picsum — just swap the URL and add an Authorization header.

Here's how to get all three — pick any one, they're all free:

Unsplash

Go to https://unsplash.com/developers
Click "Register as a developer" → create an account if needed
Click "New Application" → accept terms → give it any name/description
Your Access Key is shown immediately on the app page
Free tier: 50 requests/hour
Pexels

Go to https://www.pexels.com/api
Click "Get Started" → create a free account
Fill in the short form (app name, description, how you'll use it)
Your API Key is shown immediately — no approval wait
Free tier: 200 requests/hour
Pixabay

Go to https://pixabay.com/api/docs
Create a free account at pixabay.com
Log in and visit https://pixabay.com/api/docs — your key is shown at the top of the page automatically
Free tier: 100 requests/minute
Pexels is the fastest — key is instant, no wait, generous limit. Once you have any of them, paste the key here and I'll wire it in.