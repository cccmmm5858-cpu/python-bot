import telebot
print("DEBUG: Starting bot.py...")
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import pandas as pd
import os
import sys
import datetime
import time
from functools import lru_cache

# استيراد الوحدات
from config import TRANSIT_PLANETS, TRANSIT_TIMEFRAMES, ZODIAC_SIGNS, ASPECTS, TOKEN, ALLOWED_USERS
from dignity import get_sign_name, get_sign_degree, format_planet_position
from rating import calculate_opportunity_rating
from transits import calc_transit_to_transit, get_current_planetary_positions, angle_diff, get_aspect_details
from moon_trading import check_moon_intraday, scan_moon_day, get_moon_position_interpolated
from astro_rules import *

# ==========================================
# 1. إعدادات البوت
# ==========================================

try:
    bot = telebot.TeleBot(TOKEN)
    bot.remove_webhook()
except Exception as e:
    print(f"خطأ في التوكن: {e}")
    sys.exit(1)

# ==========================================
# 2. المتغيرات العامة
# ==========================================

GLOBAL_STOCK_DF: pd.DataFrame | None = None
GLOBAL_TRANSIT_DF: pd.DataFrame | None = None
GLOBAL_MOON_DF: pd.DataFrame | None = None

# ==========================================
# 3. تحميل البيانات
# ==========================================

def load_data_once():
    """تحميل بيانات الأسهم والعبور والقمر مرة واحدة وتخزينها في المتغيرات العامة."""
    global GLOBAL_STOCK_DF, GLOBAL_TRANSIT_DF, GLOBAL_MOON_DF
    print("Loading data...")

    if not os.path.exists("Stock.xlsx") or not os.path.exists("Transit.xlsx"):
        print("Files not found! (Stock.xlsx / Transit.xlsx)")
        return False

    try:
        # Stock
        xls = pd.ExcelFile("Stock.xlsx")
        frames = []
        for sh in xls.sheet_names:
            df = xls.parse(sh, header=0)
            if df.shape[1] < 4:
                continue
            tmp = df.iloc[:, :4].copy()
            tmp.columns = ["السهم", "الكوكب", "البرج", "الدرجة الفلكية"]
            tmp["السهم"] = tmp["السهم"].fillna(sh).replace("", sh)
            tmp = tmp.dropna(subset=["الدرجة الفلكية"])
            tmp["الدرجة الفلكية"] = pd.to_numeric(tmp["الدرجة الفلكية"], errors='coerce')
            tmp = tmp.dropna(subset=["الدرجة الفلكية"])
            frames.append(tmp)

        if frames:
            GLOBAL_STOCK_DF = pd.concat(frames, ignore_index=True)
            print(f"Stock data loaded: {len(GLOBAL_STOCK_DF)} rows.")
        else:
            GLOBAL_STOCK_DF = None
            print("No valid data in Stock.xlsx")

        # Transit
        df_trans = pd.read_excel("Transit.xlsx")
        df_trans["Datetime"] = pd.to_datetime(df_trans["Datetime"], errors="coerce")
        GLOBAL_TRANSIT_DF = df_trans.dropna(subset=["Datetime"])
        print(f"Transit data loaded: {len(GLOBAL_TRANSIT_DF)} rows.")

        # Moon
        if os.path.exists("Moon.xlsx"):
            df_moon = pd.read_excel("Moon.xlsx")
            df_moon["Datetime"] = pd.to_datetime(df_moon["Datetime"], errors="coerce")
            GLOBAL_MOON_DF = df_moon.dropna(subset=["Datetime"])
            print(f"Moon data loaded: {len(GLOBAL_MOON_DF)} rows.")
        else:
            print("Moon.xlsx not found! Moon trading will be disabled.")
            GLOBAL_MOON_DF = None

        return True

    except Exception as e:
        print(f"Error loading data: {e}")
        GLOBAL_STOCK_DF = None
        GLOBAL_TRANSIT_DF = None
        GLOBAL_MOON_DF = None
        return False


def reload_data():
    """إعادة تحميل البيانات وتحديث المتغيرات العامة."""
    return load_data_once()

# ==========================================
# 4. حساب العلاقات (Transit to Natal)
# ==========================================

def calc_aspects(stock_name: str, target_date: datetime.date):
    """حساب علاقات كواكب العبور مع كواكب السهم ليوم محدد."""
    if GLOBAL_STOCK_DF is None or GLOBAL_TRANSIT_DF is None:
        return [], stock_name

    start_dt = datetime.datetime.combine(target_date, datetime.time.min)
    end_dt = datetime.datetime.combine(target_date, datetime.time.max)

    # البحث عن السهم (contains لتقبل الاسم الجزئي)
    mask_stock = GLOBAL_STOCK_DF["السهم"].astype(str).str.contains(stock_name, case=False, regex=False)
    sdf = GLOBAL_STOCK_DF.loc[mask_stock].copy()

    if sdf.empty:
        return [], stock_name

    mask_time = (GLOBAL_TRANSIT_DF["Datetime"] >= start_dt) & (GLOBAL_TRANSIT_DF["Datetime"] <= end_dt)
    tdf = GLOBAL_TRANSIT_DF.loc[mask_time].copy()

    if tdf.empty:
        return [], sdf["السهم"].iloc[0]

    results = []
    for _, srow in sdf.iterrows():
        for _, trow in tdf.iterrows():
            for t_name, col, t_icon in TRANSIT_PLANETS:
                # 1. Exclude Moon from Stock Analysis
                if t_name in ["Moon", "القمر"]:
                    continue

                if col not in trow or pd.isna(trow[col]):
                    continue

                try:
                    transit_deg = float(trow[col])
                    natal_deg = float(srow["الدرجة الفلكية"])
                except Exception:
                    continue

                ang = angle_diff(natal_deg, transit_deg)
                asp, exact, dev, icon, asp_type, is_applying = get_aspect_details(ang)

                if asp:
                    # 2. Node Logic: Ignore Opposition if Node involved
                    if "Node" in t_name or "العقدة" in t_name:
                        if exact == 180:  # Opposition
                            continue

                    # 3. Activation Window (1 Degree Rule) & Action/Reaction
                    ar_status, ar_desc = get_action_reaction_status(dev, is_applying)
                    if not ar_status: # Skip if deviation > 1.0
                        continue

                    # 4. Apply Meanings & Special Rules
                    planet_meaning = PLANET_MEANINGS.get(t_name, "")
                    aspect_meaning = ASPECT_MEANINGS.get(asp, "")
                    
                    # Neptune Rule
                    neptune_note = check_neptune_rule(t_name, asp, asp_type)
                    
                    # Mars Rule
                    mars_note = check_mars_rule(t_name, asp)
                    
                    # Entry Signal
                    entry_signal = get_entry_signal(asp, dev, is_applying)

                    # Construct Note
                    full_note = f"{ar_status}"
                    if neptune_note: full_note += f" | {neptune_note}"
                    if mars_note: full_note += f" | {mars_note}"
                    if entry_signal: full_note += f" | {entry_signal}"

                    results.append({
                        "السهم": srow["السهم"],
                        "كوكب السهم": srow["الكوكب"],
                        "برج السهم": srow["البرج"],
                        "كوكب العبور": t_name,
                        "رمز العبور": t_icon,
                        "العلاقة": asp,
                        "الزاوية التامة": exact,
                        "الرمز": icon,
                        "النوع": asp_type,
                        "ملاحظة": full_note,
                        "معنى_الكوكب": planet_meaning,
                        "معنى_الزاوية": aspect_meaning,
                        "درجة المولد": natal_deg,
                        "درجة العبور": transit_deg,
                        "الوقت": trow["Datetime"],
                        "deviation": dev,
                        "is_applying": is_applying
                    })

    return results, sdf["السهم"].iloc[0]


# كاش للنتائج اليومية لكل سهم
@lru_cache(maxsize=2000)
def cached_calc_aspects(stock_name: str, date_str: str):
    target_date = datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
    return calc_aspects(stock_name, target_date)


def analyze_stock(stock_name: str, target_date: datetime.date):
    """تحليل سهم معين ليوم محدد مع استخدام الكاش."""
    if GLOBAL_STOCK_DF is None or GLOBAL_TRANSIT_DF is None:
        return [], stock_name

    date_str = target_date.strftime("%Y-%m-%d")
    results, real_name = cached_calc_aspects(stock_name, date_str)
    return results, real_name

# ==========================================
# 5. تنسيق رسالة تحليل السهم
# ==========================================

def format_msg(stock_name: str, results: list, target_date: datetime.date):
    """تنسيق رسالة تحليل السهم مع التقييم والحالات."""
    if not results:
        return f"لا توجد زوايا فلكية لسهم {stock_name} بتاريخ {target_date.strftime('%Y-%m-%d')}."

    # حساب التقييم العام للسهم
    stars, rating_text, score = calculate_opportunity_rating(results)

    # حساب الزمن العام (Transit to Transit)
    # تحويل التاريخ إلى datetime لتجنب خطأ DatetimeArray
    target_dt = datetime.datetime.combine(target_date, datetime.time(12, 0))
    transit_aspects = calc_transit_to_transit(GLOBAL_TRANSIT_DF, target_dt)
    gen_score = 0
    for t_asp in transit_aspects:
        if t_asp.get('النوع') == 'positive':
            gen_score += 1
        elif t_asp.get('النوع') == 'negative':
            gen_score -= 1

    gen_rating = "positive" if gen_score >= 0 else "negative"
    stock_rating = "positive" if score >= 0 else "negative"

    if gen_rating == "negative" and stock_rating == "positive":
        combined_status = "⚠️ الحركة ضعيفة (الزمن العام سلبي)"
    elif gen_rating == "negative" and stock_rating == "negative":
        combined_status = "⛔ طحن خطر (الزمن العام والسهم سلبيان)"
    elif gen_rating == "positive" and stock_rating == "positive":
        combined_status = "🚀 صعود (الزمن العام والسهم إيجابيان)"
    else:
        combined_status = "⚖️ متباين"

    header = (
        f"📌 **السهم:** {stock_name}\n"
        f"📅 **التاريخ:** {target_date.strftime('%Y-%m-%d')}\n"
        f"🧠 **تقييم الفرصة:** {stars} ({rating_text})\n"
        f"📊 **الوضع العام:** {combined_status}\n\n"
        f"──────────────\n\n"
        f"🎯 **الفواصل للزوايا السلبية والإيجابية هذا اليوم:**\n\n"
    )

    df = pd.DataFrame(results).sort_values("الوقت")
    groups = df.groupby(["كوكب العبور", "كوكب السهم", "العلاقة"])

    lines = [header]

    for (tplanet, nplanet, aspect), g in groups:
        start_time = g.iloc[0]["الوقت"]
        end_time = g.iloc[-1]["الوقت"]
        best_row = g.loc[g['deviation'].idxmin()]
        exact_time = best_row["الوقت"]

        t_deg = best_row['درجة العبور']
        n_deg = best_row['درجة المولد']
        icon = best_row['الرمز']
        
        # New Fields
        p_meaning = best_row.get('معنى_الكوكب', '')
        a_meaning = best_row.get('معنى_الزاوية', '')
        note = best_row.get('ملاحظة', '')

        transit_pos = format_planet_position(tplanet, t_deg)
        natal_sign = get_sign_name(n_deg)
        natal_deg = int(get_sign_degree(n_deg))

        is_continuous = (end_time - start_time).total_seconds() > 86400

        if is_continuous:
            time_text = "⏰ 🔄 مستمر طوال اليوم"
        else:
            # New Time Format: 10:00 AM - 02:00 PM (Target: 12:00 PM)
            time_text = (
                f"⏰ {start_time.strftime('%I:%M %p')} - {end_time.strftime('%I:%M %p')} "
                f"(الذروة: {exact_time.strftime('%I:%M %p')})"
            )

        # Integrated Meaning into Status/Description
        # Example: "Square (Restriction)"
        aspect_desc = f"{aspect}"
        if a_meaning:
            aspect_desc += f" ({a_meaning})"

        block = (
            f"🔹 **{tplanet}** (العبور) {aspect_desc} {icon} **{nplanet}** (السهم)\n"
            f"   🔸 {transit_pos}\n"
            f"   🔸 {nplanet} في {natal_sign} {natal_deg}°\n"
            f"   � **الحالة:** {note} {p_meaning}\n" # Combined Note + Planet Meaning
            f"   ⏱️ **الفريم:** {TRANSIT_TIMEFRAMES.get(tplanet, '-')}\n"
            f"   {time_text}\n\n"
        )
        lines.append(block)

    # ملخص الزمن العام
    lines.append("──────────────\n🌍 **الزمن العام (Transit to Transit):**\n")
    if not transit_aspects:
        lines.append("لا توجد علاقات عامة نشطة.\n")
    else:
        for result in transit_aspects[:5]:
            lines.append(
                f"🔹 {result['رمز1']} {result['العلاقة']} {result['الرمز']} {result['رمز2']}\n"
            )

    return "".join(lines)[:4000]

# ==========================================
# 6. تنسيق رسالة الزمن العام
# ==========================================

def format_transit_msg(target_datetime: datetime.datetime):
    """تنسيق رسالة الزمن العام (Transit to Transit)."""
    if GLOBAL_TRANSIT_DF is None:
        return "⚠️ لا توجد بيانات عبور محملة."

    # positions = get_current_planetary_positions(GLOBAL_TRANSIT_DF, target_datetime) # Removed as per request
    transit_aspects = calc_transit_to_transit(GLOBAL_TRANSIT_DF, target_datetime)

    header = (
        f"🌍 **الزمن العام - الآن**\n"
        f"📅 {target_datetime.strftime('%Y-%m-%d')} | "
        f"⏰ {target_datetime.strftime('%H:%M')}\n\n"
    )

    # Removed Positions Section

    aspects_text = "──────────────\n🔥 **العلاقات النشطة (Transit to Transit):**\n\n"
    if not transit_aspects:
        aspects_text += "لا توجد علاقات نشطة في الوقت الحالي.\n"
    else:
        for result in transit_aspects[:10]:
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

def format_moon_hourly_msg(hourly_results, sign_name, moon_deg, element, target_date):
    """تنسيق رسالة المسح الساعي للقمر."""
    header = (
        f"🌙 **المضاربة اليومية (القمر) - مسح ساعي**\n"
        f"📅 {target_date.strftime('%Y-%m-%d')}\n"
        f"🌑 **القمر في برج:** {sign_name} ({moon_deg:.2f}°)\n"
        f"Element: {element}\n\n"
        f"──────────────\n"
    )
    
    if not hourly_results:
        return header + "⚠️ لا توجد فرص مضاربة لهذا اليوم."
        
    lines = [header]
    
    for hour in sorted(hourly_results.keys()):
        data = hourly_results[hour]
        time_str = data['time'].strftime("%I:%M %p")
        opps = data['opportunities']
        
        lines.append(f"⏰ **الساعة: {time_str}**")
        for opp in opps:
            lines.append(
                f"   🔹 **{opp['السهم']}** ({opp['الكوكب']})\n"
                f"      {opp['العلاقة']} {opp['الرمز']} (انحراف: {opp['dev']:.2f}°)\n"
                f"      {opp['الحالة']}\n"
                f"      💡 {opp['النصيحة']}\n"
            )
        lines.append("") # Empty line between hours
        
    return "\n".join(lines)[:4000]

# ==========================================
# 7. لوحات المفاتيح (Keyboards)
# ==========================================

def get_main_menu():
    """القائمة الرئيسية للبوت."""
    markup = InlineKeyboardMarkup()
    markup.row(InlineKeyboardButton("📊 تحليل الأسهم", callback_data="menu:stocks"))
    markup.row(InlineKeyboardButton("🌍 الزمن العام", callback_data="menu:transits"))
    markup.row(InlineKeyboardButton("🌙 المضاربة اليومية (القمر)", callback_data="menu:moon"))
    markup.row(InlineKeyboardButton("🏭 فلترة القطاعات (جديد)", callback_data="menu:sectors"))
    
    return markup

def get_sector_keyboard():
    """لوحة مفاتيح لاختيار البرج/القطاع."""
    markup = InlineKeyboardMarkup()
    buttons = []
    # Using Arabic keys from SECTOR_MAPPING
    arabic_signs = [k for k in SECTOR_MAPPING.keys() if not k[0].isupper()] 
    
    for sign in arabic_signs:
        sector_name = SECTOR_MAPPING[sign].split(" ")[1] # Take first word of sector
        btn_text = f"{sign} ({sector_name})"
        buttons.append(InlineKeyboardButton(btn_text, callback_data=f"sector:{sign}"))
    
    for i in range(0, len(buttons), 2):
        markup.row(*buttons[i:i+2])
        
    markup.row(InlineKeyboardButton("🏠 القائمة الرئيسية", callback_data="main_menu"))
    return markup

def get_stock_keyboard():
    """لوحة مفاتيح تعرض الأسهم المتاحة."""
    markup = InlineKeyboardMarkup()
    if GLOBAL_STOCK_DF is None:
        return markup
    
    # الحصول على قائمة الأسهم الفريدة
    unique_stocks = GLOBAL_STOCK_DF["السهم"].unique()
    
    # ترتيب الأزرار (2 في كل صف)
    buttons = []
    for stock in unique_stocks:
        buttons.append(InlineKeyboardButton(stock, callback_data=f"view:{stock}:{datetime.date.today()}"))
    
    # تقسيم القائمة إلى صفوف
    for i in range(0, len(buttons), 2):
        markup.row(*buttons[i:i+2])
        
    markup.row(InlineKeyboardButton("🏠 القائمة الرئيسية", callback_data="main_menu"))
    return markup

def format_moon_msg(results, sign_name, moon_deg, element, target_date):
    """تنسيق رسالة مضاربة القمر العامة."""
    header = (
        f"🌙 **المضاربة اليومية (القمر)**\n"
        f"📅 {target_date.strftime('%Y-%m-%d')}\n"
        f"🌑 **القمر في برج:** {sign_name} ({moon_deg:.2f}°)\n"
        f"Element: {element}\n\n"
        f"──────────────\n"
    )
    
    if not results:
        return header + "⚠️ لا توجد فرص مضاربة لحظية الآن."

    lines = [header]
    for res in results:
        lines.append(
            f"🔹 **{res['السهم']}** ({res['الكوكب']})\n"
            f"   {res['العلاقة']} {res['الرمز']} (انحراف: {res['dev']:.2f}°)\n"
            f"   {res['الحالة']}\n"
            f"   💡 {res['النصيحة']}\n"
        )
    
    return "\n".join(lines)[:4000]

def get_nav_keyboard(stock_name: str, current_date_str: str):
    """أزرار التنقل بين الأيام + مضاربة القمر للسهم."""
    curr_date = datetime.datetime.strptime(current_date_str, "%Y-%m-%d").date()
    prev_date = curr_date - datetime.timedelta(days=1)
    next_date = curr_date + datetime.timedelta(days=1)

    markup = InlineKeyboardMarkup()
    markup.row(
        InlineKeyboardButton("⬅️ السابق", callback_data=f"view:{stock_name}:{prev_date}"),
        InlineKeyboardButton("التالي ➡️", callback_data=f"view:{stock_name}:{next_date}")
    )
    markup.row(
        InlineKeyboardButton("🌙 مضاربة القمر لهذا السهم", callback_data=f"moonstock:{stock_name}")
    )
    markup.row(InlineKeyboardButton("🏠 القائمة الرئيسية", callback_data="main_menu"))
    return markup

# ==========================================
# 8. أوامر الرسائل والضغطات
# ==========================================

@bot.message_handler(commands=['start'])
def start_command(message):
    print(f"DEBUG: /start command from user ID: {message.from_user.id}")
    if message.from_user.id not in ALLOWED_USERS:
        bot.reply_to(message, f"⛔ البوت للمشتركين فقط. معرفك هو: {message.from_user.id}")
        return

    welcome_text = (
        "🌟 **مرحباً بك في بوت الفلك المتقدم!**\n\n"
        "اختر ما تريد:\n"
        "📊 **تحليل الأسهم** - تحليل فلكي شامل للأسهم\n"
        "🌍 **الزمن العام** - مواقع الكواكب والعلاقات النشطة\n"
        "🌙 **المضاربة اليومية (القمر)** - تحليل حركة القمر اليومية"
    )
    try:
        bot.reply_to(message, welcome_text, reply_markup=get_main_menu(), parse_mode="Markdown")
        print("DEBUG: Welcome message sent successfully.")
    except Exception as e:
        print(f"ERROR: Failed to send welcome message: {e}")
        try:
            bot.reply_to(message, welcome_text.replace("*", ""), reply_markup=get_main_menu())
            print("DEBUG: Sent welcome message without Markdown as fallback.")
        except Exception as e2:
            print(f"ERROR: Failed to send fallback message: {e2}")


@bot.message_handler(commands=['debug'])
def debug_command(message):
    if message.from_user.id not in ALLOWED_USERS:
        return

    status_msg = "🛠 **Debug Status:**\n\n"
    
    # Check Files
    files = ["Stock.xlsx", "Transit.xlsx", "Moon.xlsx"]
    for f in files:
        exists = os.path.exists(f)
        status_msg += f"📂 `{f}`: {'✅ Found' if exists else '❌ Missing'}\n"
    
    status_msg += "\n"
    
    # Check Dataframes
    status_msg += f"📊 `GLOBAL_STOCK_DF`: {'✅ Loaded' if GLOBAL_STOCK_DF is not None else '❌ None'}\n"
    if GLOBAL_STOCK_DF is not None:
        status_msg += f"   - Rows: {len(GLOBAL_STOCK_DF)}\n"
        
    status_msg += f"🌍 `GLOBAL_TRANSIT_DF`: {'✅ Loaded' if GLOBAL_TRANSIT_DF is not None else '❌ None'}\n"
    if GLOBAL_TRANSIT_DF is not None:
        status_msg += f"   - Rows: {len(GLOBAL_TRANSIT_DF)}\n"
        
    status_msg += f"🌙 `GLOBAL_MOON_DF`: {'✅ Loaded' if GLOBAL_MOON_DF is not None else '❌ None'}\n"
    
    bot.reply_to(message, status_msg, parse_mode="Markdown")


@bot.callback_query_handler(func=lambda call: True)
def handle_query(call):
    print(f"DEBUG: Callback from user ID: {call.from_user.id}")
    if call.from_user.id not in ALLOWED_USERS:
        bot.answer_callback_query(call.id, f"⛔ غير مصرح لك. معرفك: {call.from_user.id}", show_alert=True)
        return

    data = call.data.split(":", 2)
    action = data[0]
    print(f"DEBUG: Received callback action: {action}, data: {data}")

    def answer():
        try:
            bot.answer_callback_query(call.id)
        except Exception:
            pass

    try:
        # القائمة الرئيسية
        if action == "main_menu":
            welcome_text = (
                "🌟 **بوت الفلك المتقدم**\n\n"
                "اختر ما تريد:\n"
                "📊 **تحليل الأسهم**\n"
                "🌍 **الزمن العام**\n"
                "🌙 **المضاربة اليومية (القمر)**"
            )
            try:
                bot.edit_message_text(
                    chat_id=call.message.chat.id,
                    message_id=call.message.message_id,
                    text=welcome_text,
                    reply_markup=get_main_menu(),
                    parse_mode="Markdown",
                )
            except Exception as e:
                print(f"ERROR: Failed to edit message (main_menu): {e}")
                bot.edit_message_text(
                    chat_id=call.message.chat.id,
                    message_id=call.message.message_id,
                    text=welcome_text.replace("*", ""),
                    reply_markup=get_main_menu()
                )
            answer()
            return

        # قوائم menu:stocks / menu:transits / menu:moon
        if action == "menu":
            if len(data) < 2:
                bot.answer_callback_query(call.id, "⚠️ بيانات غير مكتملة.")
                return
            menu_type = data[1]

            # قائمة الأسهم
            if menu_type == "stocks":
                if GLOBAL_STOCK_DF is None:
                    bot.answer_callback_query(call.id, "⚠️ لا توجد بيانات أسهم محملة!")
                    return
                bot.edit_message_text(
                    chat_id=call.message.chat.id,
                    message_id=call.message.message_id,
                    text="📊 **اختر سهماً لعرض تقريره الفلكي:**",
                    reply_markup=get_stock_keyboard(),
                    parse_mode="Markdown",
                )
                answer()
                return

            # الزمن العام
            if menu_type == "transits":
                if GLOBAL_TRANSIT_DF is None:
                    bot.answer_callback_query(call.id, "⚠️ لا توجد بيانات عبور محملة!")
                    return
                
                # Default to current time + 3 hours (KSA)
                target_time = datetime.datetime.now() + datetime.timedelta(hours=3)
                
                # Check if time shift is requested
                if len(data) >= 3:
                    try:
                        # Format: menu:transits:YYYY-MM-DD HH:MM
                        time_str = data[2]
                        target_time = datetime.datetime.strptime(time_str, "%Y-%m-%d %H:%M")
                    except ValueError:
                        pass

                transit_msg = format_transit_msg(target_time)
                
                # Calculate Intervals with Snap to Hour
                intervals = [1, 3, 6, 12]
                markup = InlineKeyboardMarkup()
                
                # Positive Intervals (Next)
                row_next = []
                for h in intervals:
                    # Add hours then snap to top of hour (minute=0)
                    next_t = (target_time + datetime.timedelta(hours=h)).replace(minute=0, second=0, microsecond=0)
                    row_next.append(InlineKeyboardButton(f"+{h}س", callback_data=f"menu:transits:{next_t.strftime('%Y-%m-%d %H:%M')}"))
                markup.row(*row_next)

                # Negative Intervals (Prev)
                row_prev = []
                for h in intervals:
                    # Subtract hours then snap to top of hour (minute=0)
                    prev_t = (target_time - datetime.timedelta(hours=h)).replace(minute=0, second=0, microsecond=0)
                    row_prev.append(InlineKeyboardButton(f"-{h}س", callback_data=f"menu:transits:{prev_t.strftime('%Y-%m-%d %H:%M')}"))
                markup.row(*row_prev)

                markup.row(InlineKeyboardButton("🔄 تحديث (الآن)", callback_data="menu:transits"))
                markup.row(InlineKeyboardButton("🏠 القائمة الرئيسية", callback_data="main_menu"))
                
                try:
                    bot.edit_message_text(
                        chat_id=call.message.chat.id,
                        message_id=call.message.message_id,
                        text=transit_msg,
                        reply_markup=markup,
                        parse_mode="Markdown",
                    )
                except Exception as e:
                    if "message is not modified" in str(e):
                        pass # Ignore if content is the same
                    else:
                        print(f"ERROR: Failed to send transit message: {e}")
                        # Fallback without markdown if parsing fails
                        try:
                            bot.edit_message_text(
                                chat_id=call.message.chat.id,
                                message_id=call.message.message_id,
                                text=transit_msg.replace("*", "").replace("`", ""),
                                reply_markup=markup
                            )
                        except Exception:
                            pass
                answer()
                return

            # المضاربة اليومية بالقمر (وضع عام)
            if menu_type == "moon":
                if GLOBAL_STOCK_DF is None:
                    bot.answer_callback_query(call.id, "⚠️ لا توجد بيانات أسهم محملة.")
                    return
                
                # استخدام ملف القمر إذا وجد، وإلا استخدام ملف العبور
                moon_source = GLOBAL_MOON_DF if GLOBAL_MOON_DF is not None else GLOBAL_TRANSIT_DF
                if moon_source is None:
                    bot.answer_callback_query(call.id, "⚠️ لا توجد بيانات للقمر (Moon.xlsx / Transit.xlsx).")
                    return

                # تحديد التاريخ
                if len(data) >= 3:
                    date_str = data[2]
                    try:
                        target_date = datetime.datetime.strptime(date_str, "%Y-%m-%d")
                    except ValueError:
                        target_date = datetime.datetime.now()
                else:
                    target_date = datetime.datetime.now()

                # استخدام بداية اليوم (00:00) حسب رغبة المستخدم لتوحيد القراءة
                target_date = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
                
                # تواريخ التنقل
                prev_date = target_date - datetime.timedelta(days=1)
                next_date = target_date + datetime.timedelta(days=1)

                try:
                    # استخدام المسح الساعي بدلاً من اللحظي
                    hourly_results = scan_moon_day(GLOBAL_STOCK_DF, moon_source, target_date)
                    
                    # استخراج معلومات القمر العامة (من أول نتيجة أو من الوقت الحالي)
                    if hourly_results:
                        first_hour = sorted(hourly_results.keys())[0]
                        first_entry = hourly_results[first_hour]
                        sign_name = first_entry['moon_sign']
                        moon_deg = first_entry['moon_deg']
                        element = first_entry['element']
                    else:
                        # في حال عدم وجود فرص، نحسب موقع القمر الحالي للعرض فقط
                        sign_name, moon_deg, _ = get_moon_position_interpolated(moon_source, target_date + datetime.timedelta(hours=12))
                        
                        # Calculate element
                        element = ""
                        if sign_name in ["الحمل", "الأسد", "القوس"]: element = "ناري 🔥"
                        elif sign_name in ["الثور", "العذراء", "الجدي"]: element = "ترابي ⛰️"
                        elif sign_name in ["الجوزاء", "الميزان", "الدلو"]: element = "هوائي 💨"
                        elif sign_name in ["السرطان", "العقرب", "الحوت"]: element = "مائي 💧"

                    moon_msg = format_moon_hourly_msg(hourly_results, sign_name, moon_deg, element, target_date)
                    
                    markup = InlineKeyboardMarkup()
                    markup.row(
                        InlineKeyboardButton("⬅️ السابق", callback_data=f"menu:moon:{prev_date.strftime('%Y-%m-%d')}"),
                        InlineKeyboardButton("التالي ➡️", callback_data=f"menu:moon:{next_date.strftime('%Y-%m-%d')}")
                    )
                    markup.row(InlineKeyboardButton("🏠 القائمة الرئيسية", callback_data="main_menu"))
                    
                    bot.edit_message_text(
                        chat_id=call.message.chat.id,
                        message_id=call.message.message_id,
                        text=moon_msg,
                        reply_markup=markup,
                        parse_mode="Markdown",
                    )
                except Exception as e:
                    print(f"ERROR: Moon general feature failed: {e}")
                    bot.answer_callback_query(call.id, "⚠️ تعذر حساب مضاربة القمر العامة.")
                return

        # عرض تقرير سهم ليوم معين
        if action == "view":
            if len(data) < 3:
                bot.answer_callback_query(call.id, "⚠️ بيانات غير مكتملة.")
                return

            stock_name = data[1]
            date_str = data[2]
            target_date = datetime.datetime.strptime(date_str, "%Y-%m-%d").date()

            results, stock_name_fixed = analyze_stock(stock_name, target_date)
            msg = format_msg(stock_name_fixed, results, target_date)

            markup = get_nav_keyboard(stock_name_fixed, date_str)

            try:
                bot.edit_message_text(
                    chat_id=call.message.chat.id,
                    message_id=call.message.message_id,
                    text=msg,
                    reply_markup=markup,
                    parse_mode="Markdown"
                )
            except Exception as e:
                print(f"ERROR: Failed to send stock report: {e}")
                bot.edit_message_text(
                    chat_id=call.message.chat.id,
                    message_id=call.message.message_id,
                    text=msg.replace("*", "").replace("`", ""),
                    reply_markup=markup
                )
            answer()
            return

        # مضاربة القمر لسهم محدد (ساعة-ساعة)
        if action == "moonstock":
            stock_name = data[1] if len(data) > 1 else None
            if not stock_name:
                bot.answer_callback_query(call.id, "⚠️ اسم السهم غير محدد.")
                return
            
            # تحديد التاريخ (اليوم الحالي)
            target_date = datetime.datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            
            moon_source = GLOBAL_MOON_DF if GLOBAL_MOON_DF is not None else GLOBAL_TRANSIT_DF
            if moon_source is None:
                bot.answer_callback_query(call.id, "⚠️ لا توجد بيانات للقمر.")
                return
            
            # فلترة السهم للتأكد من وجوده
            sdf = GLOBAL_STOCK_DF[GLOBAL_STOCK_DF["السهم"] == stock_name]
            if sdf.empty:
                bot.answer_callback_query(call.id, "⚠️ لا توجد بيانات لهذا السهم.")
                return

            # مسح ساعي
            try:
                hourly_results = scan_moon_day(sdf, moon_source, target_date)
                
                # الحصول على معلومات القمر من أول ساعة (إن وجدت) أو من الوقت الحالي
                if hourly_results:
                    first_entry = next(iter(hourly_results.values()))
                    sign_name = first_entry['moon_sign']
                    moon_deg = first_entry['moon_deg']
                    element = first_entry['element']
                else:
                    # إذا لم توجد نتائج، نحسب موقع القمر الحالي فقط للعرض
                    sign_name, moon_deg, _ = get_moon_position_interpolated(moon_source, datetime.datetime.now())
                    element = "" # يمكن حسابه لكن ليس ضرورياً إذا لم توجد نتائج
                
                moon_msg = format_moon_hourly_msg(hourly_results, sign_name, moon_deg, element, target_date)
                
                markup = InlineKeyboardMarkup()
                markup.row(
                    InlineKeyboardButton("🔙 رجوع للسهم", callback_data=f"view:{stock_name}:{target_date.strftime('%Y-%m-%d')}")
                )
                markup.row(InlineKeyboardButton("🏠 القائمة الرئيسية", callback_data="main_menu"))
                
                bot.edit_message_text(
                    chat_id=call.message.chat.id,
                    message_id=call.message.message_id,
                    text=moon_msg,
                    reply_markup=markup,
                    parse_mode="Markdown",
                )
            except Exception as e:
                print(f"ERROR: Moon per-stock feature failed: {e}")
                bot.answer_callback_query(call.id, "⚠️ تعذر حساب مضاربة القمر لهذا السهم.")
            return

        # إعادة تحميل البيانات
        if action == "admin" and len(data) >= 2 and data[1] == "reload":
            reload_data()
            bot.answer_callback_query(call.id, "✅ تم إعادة تحميل البيانات.")
            return

        # فلترة القطاعات
        if menu_type == "sectors":
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text="🏭 **اختر البرج لعرض أسهم القطاع المرتبط به:**",
                reply_markup=get_sector_keyboard(),
                parse_mode="Markdown",
            )
            answer()
            return

        # أمر غير معروف
        bot.answer_callback_query(call.id, "⚠️ أمر غير معروف.")
    except Exception as e:
        print(f"⚠️ Exception in handle_query: {e}")
        try:
            bot.answer_callback_query(call.id, f"⚠️ خطأ داخلي: {e}")
        except Exception:
            pass
        return

@bot.callback_query_handler(func=lambda call: call.data.startswith("sector:"))
def handle_sector_query(call):
    if call.from_user.id not in ALLOWED_USERS:
        return

    sign = call.data.split(":")[1]
    sector_desc = SECTOR_MAPPING.get(sign, "غير معروف")
    
    if GLOBAL_STOCK_DF is None:
        bot.answer_callback_query(call.id, "⚠️ لا توجد بيانات أسهم.")
        return

    # Filter stocks where Sun is in the selected Sign
    # Assuming 'الكوكب' == 'Sun' or 'الشمس' and 'البرج' == sign
    # But user said: "Stocks whose DATES are Scorpio" -> implies Sun Sign.
    # In the Excel, we have 'البرج' column. We will filter by that.
    
    # Filter for stocks in this sign (based on their Natal Sun/Sign column)
    # Note: The Excel structure has "البرج" for each row. 
    # We assume the main "Sign" of the stock is what's listed.
    
    mask = GLOBAL_STOCK_DF["البرج"] == sign
    sector_stocks = GLOBAL_STOCK_DF[mask]["السهم"].unique()
    
    if len(sector_stocks) == 0:
        bot.answer_callback_query(call.id, f"⚠️ لا توجد أسهم في برج {sign}.")
        return

    msg = (
        f"🏭 **قطاع: {sector_desc}**\n"
        f"البرج: {sign}\n"
        f"عدد الأسهم: {len(sector_stocks)}\n\n"
        f"──────────────\n"
    )
    
    # Analyze each stock briefly (Current Day)
    target_date = datetime.date.today()
    
    found_opps = False
    for stock in sector_stocks:
        results, _ = analyze_stock(stock, target_date)
        if results:
            found_opps = True
            msg += f"🔹 **{stock}**\n"
            for res in results[:2]: # Show top 2 aspects only to keep it short
                msg += f"   - {res['كوكب العبور']} {res['العلاقة']} {res['كوكب السهم']} ({res['ملاحظة']})\n"
            msg += "\n"
            
    if not found_opps:
        msg += "لا توجد فرص فلكية نشطة لهذا القطاع اليوم."

    markup = InlineKeyboardMarkup()
    markup.row(InlineKeyboardButton("🔙 قائمة القطاعات", callback_data="menu:sectors"))
    markup.row(InlineKeyboardButton("🏠 القائمة الرئيسية", callback_data="main_menu"))

    try:
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=msg[:4000],
            reply_markup=markup,
            parse_mode="Markdown",
        )
    except Exception:
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=msg[:4000].replace("*", ""),
            reply_markup=markup
        )


# ==========================================
# 9. التشغيل
# ==========================================

# ==========================================
# 9. تشغيل الويب هوك (Webhook) مع Flask
# ==========================================

from flask import Flask, request, abort

app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running", 200

@app.route('/webhook', methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return '', 200
    else:
        abort(403)

if __name__ == "__main__":
    load_data_once()
    
    # إعدادات الويب هوك
    # إعدادات الويب هوك
    # Render يوفر المتغير RENDER_EXTERNAL_URL تلقائياً
    render_url = os.environ.get('RENDER_EXTERNAL_URL') 
    
    if render_url:
        # إزالة الشرطة المائلة في النهاية إذا وجدت
        if render_url.endswith('/'):
            render_url = render_url[:-1]
            
        WEBHOOK_URL = f"{render_url}/webhook"
        print(f"Setting webhook to: {WEBHOOK_URL}")
        
        # محاولة حذف الويب هوك القديم أولاً لتجنب التعارض
        try:
            bot.remove_webhook()
            time.sleep(1)
        except Exception as e:
            print(f"Warning: Failed to remove webhook: {e}")
            
        bot.set_webhook(url=WEBHOOK_URL)
    else:
        # إذا لم نكن على Render (تجربة محلية)، يمكن استخدام Polling
        print("Running locally (Polling)...")
        bot.remove_webhook()
        bot.infinity_polling()
        sys.exit(0)

    # تشغيل سيرفر Flask
    print("Starting Flask server...")
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
