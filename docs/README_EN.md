# Telos

> **Record life. Distill cognition. Build order.**  
> **Become who you are meant to be.**

**Telos** (τέλος) is a private AI agent built exclusively for myself. It records my life, understands my state, holds my observations and reflections about the world, distills my cognition, and helps me slowly build my own inner order through a complex, lonely, and fleeting life.

---

## Core Philosophy

### This is not a productivity tool

Telos is not a to-do list, not a health tracker, not a time management app.

It is a **long-term personal system** designed to:
- Record the real trajectory of my life
- Understand my inner states
- Observe the patterns and changes of the world
- Distill the structure and principles of my cognition
- Build an order that is truly my own

### The Five Layers of Life

Telos understands "life" not as a flat list of categories, but as a five-layer structure from experience to order:

#### 1. Self
"Who am I, and what am I going through?"
- Love, loneliness, courage, willpower, resilience, fear, meaning, identity, growth

#### 2. Life
"How do I live each day well?"
- Health, learning, work, planning, habits, rhythm, efficiency, decisions

#### 3. World
"How do I observe the world around me?"
- Observations of events, understanding of people, reflections on relationships, judgments about society and reality, insights into change and patterns

#### 4. Cognition
"How do I make sense of my experiences and observations?"
- Judgment, attribution, reflection, mental models, belief updating, principle formation

#### 5. Order
"How do I form a stable inner structure over time?"
- Rhythm, principles, methods, decision frameworks, self-discipline, long-term direction, inner stability

These five layers form a complete chain:

> **Experience → Perception → Observation → Cognition → Order**

---

## Why Self-Use

Telos is a **self-use product**. Its only user is its creator.

**1. Because "I" am the most complex, long-term, and worthwhile subject to understand**
- My life is not a standardized set of requirements — it is a continuously evolving whole
- Many truly important questions cannot be abstracted into generic product features
- Only in self-use mode can the system evolve around "who I am"

**2. Because life data demands the highest level of trust**
- This system records not just tasks and health, but loneliness, fear, willpower, observations, reflections, and cognition
- These are more private and fragile than typical productivity data
- Full data ownership is the only way the system can hold authentic life material

**3. Because this is a system that grows over time**
- Its value lies not in a single use, but in long-term accumulation
- The more complete the data, the better the Agent understands my rhythms, patterns, struggles, and growth
- It is not a one-time tool — it is a long-term symbiotic system

**4. Because I am the most direct testing ground**
- I can immediately judge whether a suggestion has real value
- I can feel whether the system truly understands me
- I can iterate fast, unconstrained by generalization requirements

---

## Core Capabilities

### Phase 1: Health Dimension (Implemented)

**Recording**:
- Workouts (type, duration, distance, intensity)
- Meals (meal type, food items, calories)
- Body metrics (weight, body fat, sleep)
- Status & mood (mood, energy, stress)
- Goal setting (weight loss, muscle gain, race prep)

**Querying**:
- Time-range queries for workouts, meals, body metrics
- Multi-dimensional daily summaries

**Management**:
- Edit / delete records
- Personalized training plan generation

**Decision-making** (In Development):
- Workout suggestions based on history and goals
- Meal suggestions based on targets and daily intake
- Recovery reminders based on training load
- Goal tracking with progress analysis
- Long-term trend insights

### Phase 2: Multi-Dimensional Expansion (Planned)

- **Learning**: Book / course / skill tracking + review reminders
- **Work**: Task / meeting / retrospective tracking + time analysis
- **Emotion**: Mood / energy tracking + pattern recognition

### Phase 3: Cross-Dimensional Intelligence (Planned)

- Cross-dimensional correlation analysis (exercise & mood, sleep & efficiency)
- Holistic balance suggestions
- Monthly life retrospectives

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                   Telos - Personal Life Agent               │
├─────────────────────────────────────────────────────────────┤
│  Five Layers of Life                                        │
│  ┌─────────────────────────────────────────────────────┐  │
│  │  Self      → love, loneliness, courage, will, fear  │  │
│  │  Life      → health, learning, work, planning       │  │
│  │  World     → observation, insight, reality, change  │  │
│  │  Cognition → judgment, reflection, models, beliefs  │  │
│  │  Order     → rhythm, principles, frameworks, growth │  │
│  └─────────────────────────────────────────────────────┘  │
├─────────────────────────────────────────────────────────────┤
│  AutoAgent Layer                                            │
│  ┌─────────────────────────────────────────────────────┐  │
│  │ Interaction → Decision → Memory → Evolution         │  │
│  └─────────────────────────────────────────────────────┘  │
├─────────────────────────────────────────────────────────────┤
│  Personal Profile                                           │
│  Values · Goals · Behavior Patterns · Cognition · Order    │
└─────────────────────────────────────────────────────────────┘
```

### Core Modules

**Interaction Layer** (Completed)
- Natural Language Understanding (NLU)
- Multi-turn dialogue management
- Intent recognition & routing
- Emotionally aware responses

**Decision Layer** (In Development)
- History-based intelligent suggestions
- Cross-dimensional correlation analysis
- Proactive reminders & interventions
- Goal tracking & adjustment

**Memory Layer** (Designed)
- Elastic Memory Orchestrator (EMO)
- Long-term user profile
- Cross-session context

**Evolution Layer** (Designed)
- Cognition patch generation & gradual rollout
- Behavioral pattern learning
- Continuous decision quality improvement

---

## Tech Stack

- **Backend**: Python + FastAPI
- **Database**: MySQL (structured data)
- **AI**: LangChain + DeepSeek / OpenAI
- **Frontend**: React Native (cross-platform)
- **Deployment**: Docker + K8s

---

## Getting Started

```bash
# Clone the project
git clone https://github.com/yourusername/telos.git
cd telos

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your API keys

# Start the service
python -m src.main
```

---

## Success Criteria

This system's success is not measured by user count, engagement, or business metrics.

There is only one criterion:

> **Do I use it every day? Do I feel I can't live without it? Has it truly helped me become a better version of myself?**

---

## License

MIT License — This project is built for myself, but if it inspires you, feel free to reference and adapt.

---

**Telos** — Become who you are meant to be.
