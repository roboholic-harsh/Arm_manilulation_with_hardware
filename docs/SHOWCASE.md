<h1 align="center">🤖 Dofbot AI</h1>
<h3 align="center">Talk to Your Robot. It Just Works.</h3>

<p align="center">
  <em>An AI-powered natural language interface for industrial robotics — eliminating the need for programming expertise to operate robotic arms.</em>
</p>

---

## ❌ The Problem

**Industrial robots are powerful but incredibly hard to program.**

Today, operating a robotic arm on a factory floor requires:

- 🎓 **Specialized engineers** trained in proprietary languages (RAPID, KRL, URScript)
- ⏱️ **Hours to days** to program even simple pick-and-place routines
- 💰 **$80–200/hr** for a robotics programmer, often with weeks of lead time
- 🛑 **Extended downtime** every time a task changes — production stops while engineers reprogram

> **The result?** Small and mid-size manufacturers avoid automation entirely, and large factories lose millions in downtime during retooling.

### The Cost of Complexity

| Scenario | Traditional Approach | Time Lost |
|----------|---------------------|-----------|
| New product line setup | Hire integrator, reprogram robot | **2–6 weeks** |
| Simple task change (e.g., move part 5cm left) | Engineer writes, tests, deploys code | **4–8 hours** |
| Emergency reconfiguration | Wait for available programmer | **1–3 days** |
| Training a new operator | Months of programming courses | **3–6 months** |

---

## ✅ Our Solution

**What if anyone could command an industrial robot just by talking to it?**

We built an AI agent that understands plain English instructions and autonomously plans and executes real robot motions — no code, no training, no downtime.

### Before vs. After

| | **Before (Traditional)** | **After (Dofbot AI)** |
|---|---|---|
| **Interface** | Proprietary programming language | Natural language (English) |
| **Operator skill** | Robotics engineer | Any factory worker |
| **Task change time** | Hours to days | **Seconds** |
| **Downtime for retooling** | Production stops | **Zero** — reconfigure while running |
| **Training required** | Months | **Minutes** |

---

## 🎬 Live Demo — See It In Action

### What happens when you type: *"Move the arm to 45 degrees and turn the LED green"*

<br>

**Step 1 →** You type your command in a simple chat interface

```
You: "Move joint 1 to 45 degrees and turn the LED green"
```

**Step 2 →** The AI reasons through the task autonomously

```
🤖 AI thinking: "I need to do two things:
    1. Move joint 1 to 45°
    2. Change the LED color to green"
    
🔧 Executing: move_joints → Planning path... ✅ Success
🔧 Executing: rgb_control → Setting LED to green... ✅ Success
```

**Step 3 →** The physical robot moves and the LED turns green

```
🤖 AI: "Done! I've moved joint 1 to 45° and the LED is now green."
```

**That's it.** No code written. No programming knowledge needed. The AI figured out what tools to use, planned a safe trajectory, and executed it on real hardware — all from one English sentence.

---

### More Examples — Complex Tasks from Simple Words

| What You Say | What the Robot Does |
|---|---|
| *"Go to home position"* | Plans and executes a multi-joint trajectory to the home pose |
| *"Where are your joints right now?"* | Reads live encoder values and reports back |
| *"Move to ready pose, wait 3 seconds, then go to zero"* | Executes a 3-step sequence autonomously |
| *"Turn off the motors so I can move the arm by hand"* | Disables torque for manual guidance |
| *"Turn the light red and beep the buzzer"* | Controls RGB LED and buzzer peripherals |

> The AI handles **multi-step tasks**, **sequencing**, **sensor reading**, and **peripheral control** — all from a single conversational command.

---

## 🧠 How It Works (Simple Version)

```
┌──────────────┐        ┌──────────────┐        ┌──────────────┐
│              │        │              │        │              │
│   You Type   │──────▶ │   AI Agent   │──────▶ │ Robot Moves  │
│  in English  │        │  Thinks &    │        │  Safely &    │
│              │        │  Plans       │        │  Precisely   │
└──────────────┘        └──────────────┘        └──────────────┘
     Chat UI               AI Brain              Physical Arm
  (any browser)        (understands you,         (real motors,
                       picks the right           sensors, LEDs)
                        tools to use)
```

**Three key innovations:**

1. **🗣️ Natural Language Understanding** — Powered by state-of-the-art LLMs (Google Gemini, Groq, or local models), the system truly understands intent, not just keywords.

2. **🧩 Autonomous Tool Selection** — The AI has access to 10 robot "tools" (move, sense, control LEDs, etc.) and decides which ones to use and in what order — just like a human would.

3. **🛡️ Safe Motion Planning** — Every movement is planned through an industrial-grade motion planner (MoveIt 2) that checks for collisions and finds optimal paths before moving.

---

## 📊 Key Metrics

| Metric | Value |
|--------|-------|
| **Command to execution** | < 5 seconds |
| **Supported LLM providers** | 3 (Gemini, Groq, Ollama) |
| **Robot tools available** | 10 (motion, GPIO, sensors, utilities) |
| **Max autonomous steps per command** | 15 |
| **Motion planning** | Industrial-grade (MoveIt 2) |
| **Hardware interface** | Real-time (20 Hz control loop) |
| **Setup time** | Single command launch |

---

## 🏗️ What We've Built (Proof of Concept)

Our working prototype demonstrates the full stack on a **4-DOF Yahboom Dofbot arm**:

| Layer | What It Does | Status |
|-------|-------------|--------|
| **Chat Interface** | Beautiful web-based chat UI accessible from any browser | ✅ Working |
| **AI Agent** | ReAct reasoning engine with 10 robot tools | ✅ Working |
| **Multi-LLM Support** | Hot-swappable between Gemini, Groq, and local models | ✅ Working |
| **Motion Planning** | Collision-aware trajectory planning via MoveIt 2 | ✅ Working |
| **Hardware Control** | Real-time servo control, RGB LED, buzzer, torque | ✅ Working |
| **Live Feedback** | See what the AI is doing in real-time during execution | ✅ Working |
| **Sensor Reading** | AI can query encoder positions and use them for decisions | ✅ Working |
| **Multi-Step Tasks** | "Do X, wait, then do Y" — executed autonomously | ✅ Working |

---

## 🚀 The Vision — From POC to SaaS Platform

This proof of concept is the **foundation for a much bigger product**:

### 🌐 Future Product: NLP-Controlled Robotics SaaS

A **cloud-based platform** where any industrial robot — regardless of brand — can be commanded through natural language.

```
Today (POC)                          Tomorrow (SaaS Platform)
─────────────                        ──────────────────────────

1 robot arm                    →     Any robot (UR, FANUC, ABB, KUKA...)
1 chat interface               →     Web dashboard + Mobile app + Voice
4 joints                       →     6+ DOF arms, grippers, conveyors
10 tools                       →     100+ industry-specific tools
Local setup                    →     Cloud-hosted, deploy in minutes
```

### Product Roadmap

| Phase | Deliverable |
|-------|----------|
| **Phase 1** (completed)| Working POC — NLP-controlled 4-DOF arm with AI agent |
| **Phase 2** | Voice control, vision integration, predictive maintenance |
| **Phase 3** | Universal robot adapter SDK — support UR, FANUC, ABB |
| **Phase 4** | Fleet management — control multiple robots from one interface |
| **Phase 5** | Cloud SaaS platform — multi-tenant, dashboard, analytics |


## 👥 Team

| Name | Role |
|------|------|
| **Harsh Jadav** | Full-stack robotics engineer — hardware, ROS 2, AI agent |
| **Kathan Shah** | Robotics & AI developer |


---

<p align="center">
  <br><br>
  <strong>Dofbot AI — Making Robotics as Easy as Having a Conversation.</strong>
</p>
