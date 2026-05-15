# Supplementary Audio Samples

This package contains audio recordings from τ-voice benchmark simulations, demonstrating voice agent performance across different conditions and failure modes.

## Audio Conditions

- **Clean**: Control condition with neutral American English TTS voice, no background noise
- **Realistic**: Condition with diverse accents and background noise
## Contents

| Condition | Task | Agent | Outcome |
|-----------|------|-------|---------|
| Clean | Task 14 | Gemini | Success |
| Clean | Task 49 | xAI | Transcription |
| Clean | Task 59 | OpenAI | Logical |
| Realistic | Task 14 | Gemini | Logical |
| Realistic | Task 41 | Gemini | Logical |
| Realistic | Task 68 | xAI | Transcription |

**Notes:**
- Task 14 is included in both conditions to illustrate the impact of realistic audio. The agent succeeds under clean conditions but fails under realistic conditions with noise and accents.
- Realistic Task 41 corresponds to the annotated transcript in Appendix B of the paper.

## File Structure

```
supplementary_package/
├── README.md
├── clean/
│   ├── task_14/
│   │   └── both.wav
│   ├── task_49/
│   │   └── both.wav
│   └── task_59/
│       └── both.wav
└── realistic/
    ├── task_14/
    │   └── both.wav
    ├── task_41/
    │   └── both.wav
    └── task_68/
        └── both.wav
```

## Audio Format

All files are stereo WAV recordings containing both the simulated user and the voice agent on separate channels.
