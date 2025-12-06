# ==========================================
# moon_trading.py - المضاربة اليومية على القمر (Excel Interpolation)
# ==========================================

import datetime
import pandas as pd
from config import ZODIAC_SIGNS
from transits import angle_diff, get_aspect_details

def get_moon_position_interpolated(moon_df, target_dt):
    """
    الحصول على موقع القمر للساعة المحددة (بدون تقريب إذا توفرت الساعة)
    """
    # تقريب الوقت لأقرب ساعة (لأن الملف يحتوي على بيانات كل ساعة)
    # أو يمكننا استخدام الساعة الحالية فقط (floor)
    target_hour = target_dt.replace(minute=0, second=0, microsecond=0)
    
    # محاولة العثور على الصف المطابق للساعة
    row = moon_df[moon_df["Datetime"] == target_hour]
    
    if not row.empty:
        # وجدنا الساعة بالضبط
        moon_lng = float(row.iloc[0]["Moon Lng"])
        
        # استخدام البرج من الملف إذا وجد
        if "Moon Sign" in row.columns:
            sign_name = row.iloc[0]["Moon Sign"]
            # ترجمة اسم البرج إذا كان بالإنجليزية
            english_to_arabic = {
                "Aries": "الحمل", "Taurus": "الثور", "Gemini": "الجوزاء",
                "Cancer": "السرطان", "Leo": "الأسد", "Virgo": "العذراء",
                "Libra": "الميزان", "Scorpio": "العقرب", "Sagittarius": "القوس",
                "Capricorn": "الجدي", "Aquarius": "الدلو", "Pisces": "الحوت"
            }
            sign_name = english_to_arabic.get(sign_name, sign_name)
            
            # حساب الدرجة داخل البرج
            # كل برج 30 درجة. الدرجة داخل البرج = الدرجة المطلقة % 30
            degree_in_sign = moon_lng % 30
            
            return sign_name, degree_in_sign, moon_lng
            
    # إذا لم نجد الساعة (fallback)، نستخدم المنطق القديم (Interpolation)
    # ... (يمكن إبقاؤه كاحتياط، لكن في حالتنا الملف بالساعة)
    
    # سنحاول البحث عن أقرب صف سابق
    row_prev = moon_df[moon_df["Datetime"] <= target_dt].tail(1)
    if not row_prev.empty:
         moon_lng = float(row_prev.iloc[0]["Moon Lng"])
         sign_name = row_prev.iloc[0]["Moon Sign"] if "Moon Sign" in row_prev.columns else None
         
         # ترجمة
         if sign_name:
             english_to_arabic = {
                "Aries": "الحمل", "Taurus": "الثور", "Gemini": "الجوزاء",
                "Cancer": "السرطان", "Leo": "الأسد", "Virgo": "العذراء",
                "Libra": "الميزان", "Scorpio": "العقرب", "Sagittarius": "القوس",
                "Capricorn": "الجدي", "Aquarius": "الدلو", "Pisces": "الحوت"
            }
             sign_name = english_to_arabic.get(sign_name, sign_name)

         degree_in_sign = moon_lng % 30
         return sign_name, degree_in_sign, moon_lng

    return None, 0, 0

    return name

def check_moon_intraday(stock_df, moon_df, target_date=None, transit_df=None):
    """
    فحص فرص المضاربة اللحظية للقمر مع أسهم القائمة
    """
    # تحديد التاريخ المستهدف (افتراضياً الآن بتوقيت السعودية)
    if target_date is None:
        now_ksa = datetime.datetime.now() + datetime.timedelta(hours=3)
    else:
        if isinstance(target_date, datetime.datetime):
            now_ksa = target_date
        else:
            now_ksa = datetime.datetime.combine(target_date, datetime.time(12, 0))

    sign_name, moon_deg_sign, moon_abs_deg = get_moon_position_interpolated(moon_df, now_ksa)
    
    if sign_name is None:
        return [], "غير معروف", 0, ""
    
    # تحديد عنصر البرج
    element = ""
    if sign_name in ["الحمل", "الأسد", "القوس"]:
        element = "ناري 🔥"
    elif sign_name in ["الثور", "العذراء", "الجدي"]:
        element = "ترابي ⛰️"
    elif sign_name in ["الجوزاء", "الميزان", "الدلو"]:
        element = "هوائي 💨"
    elif sign_name in ["السرطان", "العقرب", "الحوت"]:
        element = "مائي 💧"

    # --- General Warnings Check ---
    general_warnings = []
    if transit_df is not None:
        # Check for general transits at this hour
        from transits import calc_transit_to_transit
        t_aspects = calc_transit_to_transit(transit_df, now_ksa)
        for asp in t_aspects:
            if asp['النوع'] == 'negative':
                general_warnings.append(f"⚠️ تحذير عام: {asp['كوكب1']} {asp['العلاقة']} {asp['كوكب2']}")
            elif asp['النوع'] == 'positive':
                general_warnings.append(f"✅ دعم عام: {asp['كوكب1']} {asp['العلاقة']} {asp['كوكب2']}")

    results = []
    seen_opportunities = set()
    
    for _, row in stock_df.iterrows():
        stock_name = row["السهم"]
        planet_name = row["الكوكب"]
        
        try:
            stock_planet_deg = float(row["الدرجة الفلكية"])
            moon_abs_deg = float(moon_abs_deg)
        except (ValueError, TypeError):
            continue

        angle = angle_diff(moon_abs_deg, stock_planet_deg)
        
        # Strict Rule: 1.5 degree orb for detection, but filter for <= 1.0 degree Applying
        asp_name, exact, dev, icon, asp_type, is_applying = get_aspect_details(angle, orb=1.5)
        
        # الشرط: تفعيل (applying) والفرق <= 1 درجة
        if asp_name and is_applying and dev <= 1.0:
            
            norm_name = normalize_stock_name(stock_name)
            opp_key = (norm_name, planet_name, asp_name)
            
            if opp_key in seen_opportunities:
                continue
            seen_opportunities.add(opp_key)

            status = ""
            advice = ""
            
            if dev < 0.1:
                status = "🔥 **في الصميم (Now)**"
                if asp_type == "positive":
                    advice = "✅ **فرصة:** ردة فعل إيجابية متوقعة (ارتداد)"
                else:
                    advice = "⚠️ **انتبه:** ردة فعل سلبية متوقعة (جني أرباح)"
            else:
                status = "⏳ **تفعيل (قادم للصميم)**"
                if asp_type == "positive":
                    advice = "📈 **إيجابي:** السعر يتحرك مع الاتجاه"
                else:
                    advice = "📉 **سلبي:** ضغط بيعي يزداد"
            
            # Combine warnings
            note = ""
            if general_warnings:
                note = " | ".join(general_warnings)

            results.append({
                "السهم": stock_name,
                "الكوكب": planet_name,
                "العلاقة": asp_name,
                "الرمز": icon,
                "الحالة": status,
                "النصيحة": advice,
                "moon_sign": sign_name,
                "moon_deg": moon_deg_sign,
                "dev": dev,
                "element": element,
                "type": asp_type,
                "note": note
            })
            
    return results, sign_name, moon_deg_sign, element

def scan_moon_day(stock_df, moon_df, day_date, transit_df=None):
    """
    مسح شامل لليوم (24 ساعة) للبحث عن الفرص
    """
    hourly_results = {}
    start_of_day = day_date.replace(hour=0, minute=0, second=0, microsecond=0)
    
    for h in range(24):
        current_dt = start_of_day + datetime.timedelta(hours=h)
        results, sign, deg, elem = check_moon_intraday(stock_df, moon_df, current_dt, transit_df)
        
        if results:
            hourly_results[h] = {
                "time": current_dt,
                "moon_sign": sign,
                "moon_deg": deg,
                "element": elem,
                "opportunities": results
            }
            
    return hourly_results
