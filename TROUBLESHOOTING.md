# Troubleshooting

## Streamlit UI — output folder created in the wrong directory

**Symptom:** The UI generates a video successfully but the `output/` folder appears somewhere unexpected (e.g. your home directory), or the in-browser video player shows an error opening the file.

**Cause:** `VideoOrchestrator(output_dir="output")` uses a relative path. Streamlit resolves it relative to the working directory at launch time, not relative to the project root.

**Fix:** Always launch the UI from the project root:

```bash
# from /root/a_VIDEO_GENERATION/VIDEO_DESDE_PERSONAS/VideoCreation
python -m streamlit run src/ui.py
```

Do not run it as `streamlit run src/ui.py` from a parent or unrelated directory.
