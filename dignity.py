# ==========================================
# dignity.py - حسابات الكرامات الفلكية
# ==========================================

from config import PLANETARY_DIGNITY, DIGNITY_ICONS, ZODIAC_SIGNS

def get_sign_name(degree):
    """تحديد البرج من الدرجة الفلكية"""
    try:
        return ZODIAC_SIGNS[int(degree // 30) % 12]
    except:
        return ""

def get_sign_degree(degree):
    """تحديد الدرجة داخل البرج (0-29)"""
    return degree % 30

def get_sign_element(sign_name):
    """تحديد عنصر البرج"""
    elements = {
        "الحمل": "ناري 🔥", "الأسد": "ناري 🔥", "القوس": "ناري 🔥",
        "الثور": "ترابي ⛰️", "العذراء": "ترابي ⛰️", "الجدي": "ترابي ⛰️",
        "الجوزاء": "هوائي 🌬️", "الميزان": "هوائي 🌬️", "الدلو": "هوائي 🌬️",
        "السرطان": "مائي 💧", "العقرب": "مائي 💧", "الحوت": "مائي 💧"
    }
    return elements.get(sign_name, "")

def get_planet_dignity(planet_name, sign_name):
    """
    تحديد حالة الكوكب في البرج
    Returns: (حالة, رمز) أو (None, None)
    """
    if planet_name not in PLANETARY_DIGNITY:
        return None, None
    
    dignity_data = PLANETARY_DIGNITY[planet_name]
    
    for dignity_type, dignity_sign in dignity_data.items():
        if dignity_sign == sign_name:
            icon = DIGNITY_ICONS.get(dignity_type, "")
            return dignity_type, icon
    
    return None, None

def format_planet_position(planet_name, degree):
    """
    تنسيق موقع الكوكب مع حالته
    مثال: "القمر في الجدي 29° (في وباله ⚠️)"
    """
    sign = get_sign_name(degree)
    sign_deg = int(get_sign_degree(degree))
    
    dignity, icon = get_planet_dignity(planet_name, sign)
    
    base_text = f"{planet_name} في {sign} {sign_deg}°"
    
    if dignity:
        return f"{base_text} (في {dignity}ه {icon})"
    else:
        return base_text
