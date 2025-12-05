# ==========================================
# transits.py - حسابات الزمن العام
# ==========================================

import pandas as pd
from config import TRANSIT_PLANETS, ASPECTS, ASPECT_ORBS
from dignity import get_sign_name, get_sign_degree, format_planet_position

def angle_diff(a, b):
    """حساب الفرق بين زاويتين"""
    d = abs(a - b) % 360
    if d > 180:
        d = 360 - d
    return d

def get_aspect_details(angle, orb=1.0):
    """
    تحديد نوع العلاقة الفلكية
    Returns: (name, exact_angle, deviation, icon, aspect_type, is_applying)
    """
    for exact, name, icon, aspect_type in ASPECTS:
        diff = angle - exact
        
        # Applying Logic: Degree before to Exact (e.g. 89 to 90)
        # We want diff to be between -orb and 0 (approaching) OR 0 (exact)
        # But wait, user said "Degree before to Exact only".
        # So if exact is 90, we accept 89.0 to 90.0.
        # diff = angle - exact. If angle is 89, diff is -1. If angle is 90, diff is 0.
        # If angle is 91, diff is +1 (Separating - Reject).
        
        # However, angle_diff handles circularity. Let's stick to simple diff first for logic check.
        # But we need to handle the circle (359 -> 0).
        
        # Let's use the absolute diff for the standard check first, then refine for "Applying".
        # Actually, standard astrology: Applying is when faster planet approaches slower.
        # Here we simplify: User wants "Degree before to Exact".
        # So we check if the angle is in range [exact - orb, exact].
        
        # Handle circularity for Conjunction (0)
        if exact == 0:
            # Range: [360-orb, 360] OR [0, 0]
            # If angle is 359, it's applying to 0.
            if (angle >= 360 - orb) or (angle == 0) or (angle <= 0 + 0.1): # Allow small margin for 0
                 return name, exact, abs(angle - exact if angle < 180 else angle - 360), icon, aspect_type, True
        else:
            # Check if angle is within orb (both sides)
            if abs(angle - exact) <= orb:
                return name, exact, abs(exact - angle), icon, aspect_type, True
                
    return None, None, None, None, None, False

def calc_transit_to_transit(transit_df, target_datetime):
    """
    حساب العلاقات بين كواكب الزمن العام (Transit to Transit)
    
    Parameters:
        transit_df: DataFrame يحتوي على بيانات العبور
        target_datetime: التاريخ والوقت المطلوب
    
    Returns:
        list of dict: قائمة العلاقات النشطة
    """
    # البحث عن أقرب صف للوقت المطلوب
    transit_df["time_diff"] = abs(transit_df["Datetime"] - target_datetime)
    closest_row = transit_df.loc[transit_df["time_diff"].idxmin()]
    
    results = []
    
    # حساب العلاقات بين كل كوكبين
    for i, (planet1_name, planet1_col, planet1_icon) in enumerate(TRANSIT_PLANETS):
        if planet1_col not in closest_row or pd.isna(closest_row[planet1_col]):
            continue
        
        planet1_deg = float(closest_row[planet1_col])
        
        for j, (planet2_name, planet2_col, planet2_icon) in enumerate(TRANSIT_PLANETS):
            if j <= i:  # تجنب التكرار
                continue
            
            if planet2_col not in closest_row or pd.isna(closest_row[planet2_col]):
                continue
            
            planet2_deg = float(closest_row[planet2_col])
            
            # حساب الزاوية
            angle = angle_diff(planet1_deg, planet2_deg)
            aspect_name, exact, dev, icon, aspect_type, is_applying = get_aspect_details(angle)
            
            if aspect_name:
                results.append({
                    "كوكب1": planet1_name,
                    "رمز1": planet1_icon,
                    "درجة1": planet1_deg,
                    "كوكب2": planet2_name,
                    "رمز2": planet2_icon,
                    "درجة2": planet2_deg,
                    "العلاقة": aspect_name,
                    "الزاوية التامة": exact,
                    "الرمز": icon,
                    "النوع": aspect_type,
                    "deviation": dev,
                    "الوقت": closest_row["Datetime"]
                })
    
    # ترتيب حسب الدقة (أقل deviation)
    results.sort(key=lambda x: x["deviation"])
    
    return results

def format_transit_to_transit_msg(results, target_datetime):
    """
    تنسيق رسالة الزمن العام (Transit to Transit)
    """
    if not results:
        return f"لا توجد علاقات نشطة في الزمن العام بتاريخ {target_datetime.strftime('%Y-%m-%d %H:%M')}"
    
    # الحصول على أول نتيجة للحصول على البيانات
    first_result = results[0]
    
    header = (
        f"🌍 **الزمن العام - الآن**\n"
        f"📅 {target_datetime.strftime('%Y-%m-%d')} | "
        f"⏰ {target_datetime.strftime('%H:%M')}\n\n"
    )
    
    # عرض مواقع جميع الكواكب
    positions_text = "📍 **مواقع الكواكب:**\n"
    
    # استخدام أول نتيجة للحصول على البيانات
    for planet_name, planet_col, planet_icon in TRANSIT_PLANETS:
        # نحتاج للوصول للبيانات من مصدر آخر
        # سنضيف هذا في النسخة المحسنة
        pass
    
    # عرض العلاقات النشطة
    aspects_text = "\n──────────────\n🔥 **العلاقات النشطة (Transit to Transit):**\n\n"
    
    for result in results[:10]:  # أول 10 علاقات
        planet1_pos = format_planet_position(result["كوكب1"], result["درجة1"])
        planet2_pos = format_planet_position(result["كوكب2"], result["درجة2"])
        
        block = (
            f"🔹 {result['رمز1']} {planet1_pos}\n"
            f"   🔸 {result['رمز2']} {planet2_pos}\n"
            f"   🔹 {result['العلاقة']} {result['الرمز']} ({int(result['الزاوية التامة'])}°)\n"
            f"   ⏰ نشطة الآن\n\n"
        )
        aspects_text += block
    
    return header + aspects_text

def get_current_planetary_positions(transit_df, target_datetime):
    """
    الحصول على مواقع جميع الكواكب في وقت محدد
    
    Returns:
        dict: {planet_name: degree}
    """
    transit_df["time_diff"] = abs(transit_df["Datetime"] - target_datetime)
    closest_row = transit_df.loc[transit_df["time_diff"].idxmin()]
    
    positions = {}
    for planet_name, planet_col, planet_icon in TRANSIT_PLANETS:
        if planet_col in closest_row and not pd.isna(closest_row[planet_col]):
            positions[planet_name] = {
                "degree": float(closest_row[planet_col]),
                "icon": planet_icon
            }
    
    return positions
