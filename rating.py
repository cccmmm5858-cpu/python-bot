# ==========================================
# rating.py - نظام تقييم الفرص
# ==========================================

from config import BENEFIC_PLANETS, MALEFIC_PLANETS

def calculate_opportunity_rating(aspects_list):
    """
    حساب تقييم الفرصة بناءً على العلاقات الفلكية
    
    Parameters:
        aspects_list: قائمة العلاقات من calc_aspects
    
    Returns:
        (stars, rating_text, score)
    """
    if not aspects_list:
        return "⭐", "لا توجد علاقات", 0
    
    score = 0
    positive_count = 0
    negative_count = 0
    
    for aspect in aspects_list:
        aspect_name = aspect.get("العلاقة", "")
        transit_planet = aspect.get("كوكب العبور", "")
        natal_planet = aspect.get("كوكب السهم", "")
        
        # التثليث (120°) - أقوى علاقة إيجابية
        if aspect_name == "تثليث":
            score += 3
            positive_count += 1
            
            # مكافأة إضافية للكواكب المفيدة
            if transit_planet in BENEFIC_PLANETS:
                score += 1
            if natal_planet in BENEFIC_PLANETS:
                score += 1
        
        # الاقتران (0°) - يعتمد على الكواكب
        elif aspect_name == "اقتران":
            if transit_planet in BENEFIC_PLANETS or natal_planet in BENEFIC_PLANETS:
                score += 2
                positive_count += 1
            elif transit_planet in MALEFIC_PLANETS or natal_planet in MALEFIC_PLANETS:
                score -= 1
                negative_count += 1
            else:
                score += 1
                positive_count += 1
        
        # التربيع (90°) والمقابلة (180°) - علاقات صعبة
        elif aspect_name in ["تربيع", "مقابلة"]:
            score -= 2
            negative_count += 1
            
            # عقوبة إضافية للكواكب الضارة
            if transit_planet in MALEFIC_PLANETS:
                score -= 1
            if natal_planet in MALEFIC_PLANETS:
                score -= 1
    
    # تحديد النجوم والنص
    if score >= 8:
        stars = "⭐⭐⭐⭐⭐"
        rating_text = "فرصة ذهبية!"
    elif score >= 5:
        stars = "⭐⭐⭐⭐"
        rating_text = "فرصة ممتازة"
    elif score >= 2:
        stars = "⭐⭐⭐"
        rating_text = "فرصة جيدة"
    elif score >= 0:
        stars = "⭐⭐"
        rating_text = "فرصة متوسطة"
    else:
        stars = "⭐"
        rating_text = "فرصة ضعيفة"
    
    return stars, rating_text, score

def get_rating_summary(positive_count, negative_count):
    """ملخص سريع للتقييم"""
    if positive_count > negative_count * 2:
        return "📈 طاقة إيجابية قوية"
    elif positive_count > negative_count:
        return "📊 طاقة إيجابية معتدلة"
    elif positive_count == negative_count:
        return "⚖️ طاقة متوازنة"
    elif negative_count > positive_count:
        return "📉 طاقة صعبة"
    else:
        return "⚠️ طاقة تحدي"
