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
            "Register that the user ate (or will eat) something outside the plan. "
            "Returns {id: int}. After this succeeds you MUST call recalculate_plan(deviation_id=<that id>) "
            "as the next step — never call get_week_plan or build_meal_plan after register_deviation."
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
        "name": "get_week_plan",
        "description": (
            "Get the full active week plan with all days and meals (including meal IDs). "
            "Use this when you need to find a specific meal to modify/move/skip. "
            "Returns days with their meal_id, date, meal_type, status, container_label, kcal."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "update_meal_status",
        "description": (
            "Mark a specific meal as eaten / skipped / planned. "
            "Use 'skipped' when the user won't eat this meal (e.g. dining out, planned skip, missed). "
            "Use 'eaten' when the user confirms they ate it. "
            "ALWAYS pair with register_deviation if the user ate something else instead, "
            "and with update_container to move the prepared food to freezer if skipped."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "meal_id": {"type": "integer", "description": "Meal ID from get_today_plan / get_week_plan"},
                "status": {
                    "type": "string",
                    "enum": ["eaten", "skipped", "planned"],
                    "description": "New status",
                },
                "reason": {
                    "type": "string",
                    "description": "Short reason (e.g. 'ужин в ресторане', 'пропустил')",
                },
            },
            "required": ["meal_id", "status"],
        },
    },
    {
        "name": "update_container",
        "description": (
            "Update a container's status / location / note. "
            "Use to move prepared food to the freezer when a meal is skipped (status='frozen'), "
            "to mark a container as eaten (status='eaten'), or to add a note about handling."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "container_label": {
                    "type": "string",
                    "description": "Container label like '1А', '2Б' (from the plan)",
                },
                "status": {
                    "type": "string",
                    "enum": ["filled", "eaten", "expired", "frozen"],
                    "description": "New status. 'frozen' = moved to freezer to extend shelf life.",
                },
                "note": {
                    "type": "string",
                    "description": "Optional note to append to the container description",
                },
            },
            "required": ["container_label"],
        },
    },
    {
        "name": "build_meal_plan",
        "description": (
            "DESTRUCTIVE: generates a brand new 7-day plan and CANCELS overlapping plans. "
            "ONLY call this when the user explicitly asks for a new plan from scratch "
            "(e.g. 'составь план на следующую неделю', 'сгенерируй новый план'). "
            "NEVER call this for adjustments, deviations, restaurant visits, skipped meals, "
            "or 'завтра планирую X' scenarios — those are handled by update_meal_status / "
            "register_deviation / recalculate_plan / update_container."
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
