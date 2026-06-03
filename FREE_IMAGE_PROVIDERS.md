To get genuinely relevant stock photos from prompts, we need a searchable API. The realistic free options:

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