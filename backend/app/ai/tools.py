"""
Tool definitions for the КБЖУЙ AI agent.
TOOLS         — Anthropic (Claude) format
TOOLS_OPENAI  — OpenAI-compatible format (used for Ollama)
"""

TOOLS: list[dict] = [
    {
        "name": "get_user_profile",
        "description": (
            "Get the user's nutritional profile: goals, weight, height, activity level, "
            "daily КБЖУ targets (kcal, protein, fat, carbs), eating schedule, and planned deviations."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "get_today_plan",
        "description": (
            "Get today's meal plan: list of meals with container labels, descriptions, "
            "locations, heating instructions, and КБЖУ per meal. Also returns today's КБЖУ totals."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "get_storage",
        "description": (
            "Get all current storage contents: containers in fridge, freezer, and pantry. "
            "Includes expiry dates, КБЖУ, and location. Use this to check what is available."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "register_deviation",
        "description": (
            "Register that the user ate something outside the plan (spontaneous deviation). "
            "This records the extra calories and enables plan recalculation. "
            "Use when user says they ate something unplanned."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "description": {
                    "type": "string",
                    "description": "What the user ate, e.g. 'пицца Маргарита (2 куска)'",
                },
                "kcal": {
                    "type": "integer",
                    "description": "Estimated extra calories from this deviation",
                },
                "protein_g": {"type": "integer", "description": "Estimated extra protein in grams"},
                "fat_g": {"type": "integer", "description": "Estimated extra fat in grams"},
                "carbs_g": {"type": "integer", "description": "Estimated extra carbs in grams"},
            },
            "required": ["description", "kcal"],
        },
    },
    {
        "name": "recalculate_plan",
        "description": (
            "After registering a deviation, recalculate the nutritional targets for the "
            "remaining days of the week. Returns adjusted daily kcal and macros."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "deviation_id": {
                    "type": "integer",
                    "description": "ID of the deviation just registered",
                },
            },
            "required": ["deviation_id"],
        },
    },
    {
        "name": "get_expiring_soon",
        "description": (
            "Get a list of items expiring within the next 2 days. "
            "Use when user asks about food that's about to go bad."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "build_meal_plan",
        "description": (
            "Generate and save a 7-day meal plan for the user based on their profile. "
            "Call this tool after reviewing the user's profile to create a personalized plan. "
            "The plan will include meals, containers, and a shopping list."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "week_start": {
                    "type": "string",
                    "description": "Start date of the plan in ISO format (YYYY-MM-DD). Use next Monday.",
                },
                "notes": {
                    "type": "string",
                    "description": "Optional notes/preferences for the plan (e.g. 'больше рыбы', 'без сложных рецептов')",
                },
            },
            "required": ["week_start"],
        },
    },
]

# OpenAI-compatible format for Ollama
TOOLS_OPENAI: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": t["name"],
            "description": t["description"],
            "parameters": t["input_schema"],
        },
    }
    for t in TOOLS
]
