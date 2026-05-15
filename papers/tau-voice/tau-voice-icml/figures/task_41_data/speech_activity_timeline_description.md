# Speech Activity Timeline — Task 41 (Retail Domain, Gemini)

This document describes the speech activity timeline visualization used as Figure 1 in the paper. The timeline shows a complete customer service interaction in the Retail domain, with the Gemini audio-native agent.

## Data Files

All source data for this figure is available in this directory:

| File | Description |
|------|-------------|
| `simulation.json` | Complete simulation data including all 898 ticks with audio chunks, effects, and metadata |
| `task.json` | Task definition including user persona, instructions, and evaluation criteria |
| `both.wav` | Stereo audio file (5.5 MB) with user on left channel, agent on right channel |
| `user_labels.txt` | Audacity-format label track with user speech segments and transcripts |
| `assistant_labels.txt` | Audacity-format label track with agent speech segments and transcripts |

### Label Track Format
The label files use Audacity's tab-separated format: `start_time<TAB>end_time<TAB>transcript`

You can import these into Audacity alongside `both.wav` to visualize the conversation.

## Scenario Overview

**Domain:** Retail  
**Agent:** Gemini Live 2.5 Flash Native Audio  
**Background Noise:** Busy Street (outdoor environment)  
**Duration:** ~179 seconds (3 minutes)  
**Task Outcome:** 0.0 reward (failed)

The user (persona: wei_lin) is calling about two issues:
1. Exchange a 1000-piece intermediate jigsaw puzzle for an easier one with fewer pieces
2. Check and correct their shipping address

## Conversation Flow

### Opening (0s - 24s)
**User (5.2s - 24.0s):** *"Hi, I have two problems. First, I ordered a 1000-piece intermediate jigsaw, but I think it's too hard for my kid—can I switch it to the easiest one with the fewest pieces? Second, I might have typed my address wrong. I want to check and maybe fix the address."*

- **Frame drops** at 6.0s and 23.4s during user speech (simulating network packet loss)
- **Agent interrupts** at 8.0s with "Hello!" (0.2s, barely audible) and at 18.8s with "I can help" (0.4s) — the agent starts speaking while the user is still talking
- At 23.0s, the agent interrupts again but continues speaking as the user yields

### Authentication (24s - 59s)
The agent asks for authentication. The user doesn't remember their email.

**User (33.8s - 35.8s):** *"I don't remember my email."*
- User **interrupts the agent** — agent does not yield initially
- **Muffling effect** applied to user speech
- **Vocal tic** (out-of-turn) at 33.0s — throat clearing before speaking

**User (41.8s - 46.6s):** *"Yeah. First name: M, E, I. Last name: P"*
- User interrupts, agent yields

**User (53.0s - 58.6s):** *"A, T, E, L. Zip code: seven, six, one, six, five."*
- **Burst noise** events at 38.2s and 51.8s (environmental car sounds)

### Task Prioritization (60s - 77s)

**User (67.8s - 69.2s):** *"Jigsaw first."*
- User **interrupts** agent to prioritize the jigsaw issue
- Agent **yields** (stops speaking at 68.0s)
- **Frame drop** at 67.8s during speech
- **NO RESPONSE:** User waits 5+ seconds but agent doesn't respond
- This is captured as a no-response error

**User (74.4s - 77.0s):** *"Can you switch it to the easiest puzzle?"*
- User speaks again without getting a response to previous utterance
- **Muffling effect** on user speech

### Non-Directed Speech Error (78s - 86s)

**Agent (78.6s - 83.2s):** Agent finally responds, asking for confirmation.

**Non-directed speech (82.4s):** *"Give me a moment."*
- User says something to someone else (not the agent)
- Agent was speaking at the time
- **Agent incorrectly yields** at 83.2s (0.8s after non-directed speech)
- This is captured as a **Non-Dir Error** on the timeline

**User (84.4s - 85.4s):** *"Yes, the one wi—"*
- User interrupted by agent at 84.4s — both start speaking simultaneously

### Puzzle Exchange Discussion (86s - 130s)

**User (93.8s - 96.2s):** *"No, I don't know the item ID."*
- User interrupts agent

**User (102.4s - 106.8s):** *"I just remember it's the 1000-piece intermediate jigsaw."*

**User (113.8s - 114.6s):** *"Yeah, that's it."*
- User interrupts — agent does not yield

**User (121.8s - 123.0s):** *"mm-hmm"*
- **Backchannel** — brief acknowledgment without taking the floor
- Agent correctly continues speaking (no backchannel error)

**User (128.2s - 129.8s):** *"Yes, please."*
- **Muffling effect**
- **NO RESPONSE** at 129.8s — agent fails to respond promptly

### Address Correction (130s - 172s)

**User (135.0s - 137.0s):** *"Now, can we check my address?"*
- **Frame drop** at 135.6s during speech

**User (145.8s - 149.4s):** *"No, it should be four, four, five, Maple Drive."*
- User interrupts to correct the address
- **Frame drop** at 147.8s during speech

**User (155.8s - 159.2s):** *"Can you make sure all my orders use that address too?"*
- User interrupts

**Burst noise** at 160.2s (environmental sound)

**User (170.2s - 171.6s):** *"Yes, update it."*

## Event Summary

### Observations (What Happened)
| Event Type | Count | Description |
|------------|-------|-------------|
| User Interruptions | 8 | User cutting in while agent speaks |
| Backchannel | 1 | "mm-hmm" acknowledgment at 121.8s |
| Burst Noise | 4 | Environmental noise (car sounds) |
| Vocal Tic | 1 | Throat clearing at 33.0s |
| Non-directed Speech | 1 | "Give me a moment" at 82.4s |
| Muffling | 3 | Audio degradation on user speech |
| Frame Drops | 12 | 150ms network packet loss events |

### Evaluations (Agent Errors)
| Event Type | Count | Description |
|------------|-------|-------------|
| Agent Interrupts | 5 | Agent started while user speaking (8.0s, 18.8s, 23.0s, 45.6s, 84.4s) |
| No-Response | 2 | Agent failed to respond (69.2s after "Jigsaw first", 129.8s after "Yes, please") |
| No-Yield | 2 | Agent didn't stop when user interrupted |
| Non-Dir Error | 1 | Agent incorrectly yielded to non-directed speech at 82.4s |

### Successful Behaviors (No Errors)
- **Backchannel handled correctly:** Agent recognized "mm-hmm" at 121.8s as a backchannel and continued speaking
- **Vocal tic handled correctly:** Agent did not treat the throat clearing at 33.0s as a turn-taking signal

## Visual Legend Guide

### Speech Tracks
- **Blue bars (top):** User speech segments with waveform overlay
- **Red bars (bottom):** Agent speech segments with waveform overlay
- **Purple overlap:** Simultaneous speech (overlap regions)

### Observation Markers (On speech tracks)
| Marker | Color | Description |
|--------|-------|-------------|
| ▼ (User Int.) | Orange | User started speaking while agent was talking |
| ○ (Backchannel) | Green | Brief acknowledgment from user |
| ⚡ (Burst) | Violet | Burst noise event (car horn, siren, etc.) |
| ~ (Vocal Tic) | Cyan | Cough, sneeze, or throat clearing |
| … (Non-Dir.) | Pink | Non-directed speech (user aside) |
| ▒ (Muffling) | Slate | Audio quality degradation |
| \| (Frame Drop) | Orange | Network packet loss (150ms) |

### Evaluation Markers (Below agent track - error indicators)
| Marker | Color | Description |
|--------|-------|-------------|
| ▲ (Agent Int.) | Red | Agent inappropriately interrupted user |
| X (No Response) | Red | Agent failed to respond after user finished |
| …X (Non-Dir Error) | Red | Agent incorrectly responded/yielded to non-directed speech |
| ~X (Voc. Tic Error) | Red | Agent incorrectly responded/yielded to vocal tic |

## Why This Example Was Selected

This simulation was chosen because it demonstrates:

1. **Rich variety of speech events:** Multiple interruptions (both user and agent), a backchannel, various audio effects (burst noise, vocal tics, non-directed speech, muffling, frame drops)

2. **Both success and failure modes:**
   - **Failures:** Agent interruptions, no-response events, non-directed speech error
   - **Successes:** Correct backchannel handling, correct vocal tic handling

3. **Realistic conversational dynamics:** Natural back-and-forth with overlapping speech, user taking initiative to interrupt and steer the conversation

4. **Full feature coverage:** All visualization elements are represented, making it ideal for illustrating the evaluation methodology

## Technical Notes

- **Tick duration:** 200ms per tick
- **Total ticks:** 897 (after filtering end-of-conversation artifact)
- **User segments:** 16
- **Agent segments:** 15
- **Simulation ID:** 39ee01bf-37ff-4330-90c2-d15f9a940de0
