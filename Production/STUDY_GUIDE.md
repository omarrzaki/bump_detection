<style>
/* الكود يفضل من الشمال لليمين حتى لو الصفحة عربي RTL */
pre, code, kbd, samp { direction: ltr; unicode-bidi: plaintext; text-align: left; }
</style>

<div dir="rtl">

# 📚 دليل مذاكرة المشروع — Speed Bump Detection System

> ملف شرح كامل للكود من الصفر. اقرأه كأنك بتبني المشروع بإيدك تاني.
> الترتيب: **الفكرة → الـ Architecture → الهاردوير → كود الراسبري باي (`run_raspberry_pi.py`) → كود السيرفر (`api_server.py`) → أسئلة المناقشة**.

---

## الفهرس

1. [الفكرة في سطر](#1-الفكرة-في-سطر)
2. [الصورة الكبيرة (Architecture)](#2-الصورة-الكبيرة-architecture)
3. [رحلة الـ Bump من الكاميرا للموبايل (Data Flow)](#3-رحلة-الـ-bump-من-الكاميرا-للموبايل)
4. [الهاردوير والـ OS](#4-الهاردوير-والـ-os)
5. [كود الراسبري باي — `run_raspberry_pi.py`](#5-كود-الراسبري-باي--run_raspberry_pipy)
6. [كود السيرفر — `api_server.py`](#6-كود-السيرفر--api_serverpy)
7. [المفاهيم اللي لازم تفهمها كويس](#7-المفاهيم-اللي-لازم-تفهمها-كويس)
8. [أسئلة المناقشة المتوقعة + الإجابات](#8-أسئلة-المناقشة-المتوقعة--الإجابات)

---

## 1. الفكرة في سطر

نظام بيكتشف **المطبات الصناعية (speed bumps)** في الشارع باستخدام **كاميرا + ذكاء اصطناعي (YOLO)**، ولما يلاقي مطب بياخد إحداثياته من **GPS** ويبعتها لـ **سيرفر**، والسيرفر بيخزّنها وبيوفّرها لـ **تطبيق موبايل** يعرضها على الخريطة عشان السواقين ياخدوا بالهم.

**ليه مفيد؟** المطبات غير الممهّدة أو غير المعلّمة بتسبب حوادث وتلف للعربيات. النظام بيعمل "خريطة مطبات" تلقائية.

---

## 2. الصورة الكبيرة (Architecture)

المشروع 3 أجزاء منفصلة بتتكلم مع بعض:

```
┌─────────────────────────────────────┐
│   1) الراسبري باي (داخل العربية)      │
│   run_raspberry_pi.py                │
│   ┌─────────┐   ┌──────┐   ┌──────┐  │
│   │ كاميرا   │──▶│ YOLO │──▶│ GPS  │  │
│   └─────────┘   └──────┘   └──────┘  │
│         يبعت المطب عن طريق HTTP        │
└──────────────────┬──────────────────┘
                   │  POST /report_bump
                   ▼
┌─────────────────────────────────────┐
│   2) السيرفر (API)                   │
│   api_server.py  (FastAPI)           │
│   - بيستقبل المطبات                   │
│   - بيشيل المكرر (deduplication)      │
│   - بيخزّن في bumps_data.json         │
└──────────────────┬──────────────────┘
                   │  GET /get_bumps
                   ▼
┌─────────────────────────────────────┐
│   3) تطبيق الموبايل (Flutter)         │
│   - بيجيب المطبات                     │
│   - بيعرضها على Google Maps          │
└─────────────────────────────────────┘
```

**نقطة مهمة للمناقشة:** ليه الأجزاء منفصلة؟
- **فصل الاهتمامات (Separation of concerns):** كل جزء له شغلانة واحدة.
- الراسبري باي والسيرفر بيشتغلوا على نفس الجهاز حالياً (`127.0.0.1`)، بس ممكن نفصلهم على جهازين من غير ما نغيّر الكود — بس نغيّر `API_URL`.
- الموبايل مش محتاج يعرف أي حاجة عن YOLO أو الكاميرا — هو بس بيقرأ JSON من الـ API.

---

## 3. رحلة الـ Bump من الكاميرا للموبايل

ده أهم جزء تفهمه — لو فهمته، فهمت المشروع كله:

```
1. الكاميرا بتصوّر frame (صورة)
        ↓
2. ناخد frame من كل 2 (PROCESS_EVERY_N_FRAMES) عشان نخفّف الحمل
        ↓
3. YOLO بيدوّر على مطبات في الـ frame ويدّي لكل واحد "نسبة ثقة" (confidence)
        ↓
4. نظام الـ tiers بيقرر: ده مطب حقيقي ولا false positive؟
        ↓
5. لو مطب → ناخد الإحداثيات من الـ GPS
        ↓
6. dedup محلي: هل سجّلنا مطب في نفس المكان قبل كده؟ (عشان منكررش)
        ↓
7. نبعت المطب للسيرفر (HTTP POST)
        ↓
8. السيرفر: dedup تاني (هل في مطب تاني قريب من 8 متر؟) → يدمج أو يضيف جديد
        ↓
9. السيرفر يخزّن في bumps_data.json
        ↓
10. الموبايل يطلب القايمة ويعرضها على الخريطة
```

لاحظ إن في **طبقتين dedup**: واحدة على الراسبري باي (نفس الجلسة) وواحدة على السيرفر (كل الأجهزة). هنرجعلهم.

---

## 4. الهاردوير والـ OS

ده الجزء اللي انت ركّبته بإيدك — مهم تعرف تتكلم فيه:

| المكوّن | التفاصيل | بيتوصّل إزاي |
|--------|---------|-------------|
| **Raspberry Pi 5 (8GB)** | الكمبيوتر اللي بيشغّل كل حاجة | — |
| **Pi Camera Module v2** (imx219) | الكاميرا | كابل ribbon (CSI) |
| **u-blox NEO-6M GPS** | بيجيب الإحداثيات | **USB** (مش GPIO) → بيظهر باسم `/dev/ttyACM0` |
| **Active Cooler** | تبريد (المعالج كان بيوصل 77°) | فوق الـ CPU |

**الـ OS:** Debian 13 (**Trixie**) — مش Bookworm. ده مهم لأن فيه فروقات:
- أوامر الكاميرا بقت `rpicam-*` بدل `libcamera-*`.
- **PEP 668**: مينفعش تثبّت pip packages على النظام مباشرة — لازم **virtual environment** (`bump_env`).
- Python **3.13**.

**ليه `--system-site-packages` في الـ venv؟** عشان الـ `picamera2` و `python3-gps` بيتثبّتوا من `apt` (مش pip)، والـ venv محتاج يشوفهم. الفلاج دي بتخلّي الـ venv يشوف باكدجات النظام.

**ليه gpsd؟** هو daemon (برنامج بيشتغل في الخلفية) بيتكلم مع الـ GPS عبر USB، وبرنامجنا بيتكلم مع gpsd (مش مع الـ GPS مباشرة). ده بيخلّي أكتر من برنامج يقدر يقرأ الـ GPS في نفس الوقت.

---

## 5. كود الراسبري باي — `run_raspberry_pi.py`

ده **قلب المشروع**. هنمشي عليه قطعة قطعة.

### 5.1 الـ Imports (الأسطر 7–20)

```python
from ultralytics import YOLO   # مكتبة الذكاء الاصطناعي (الموديل)
import cv2                      # OpenCV — معالجة الصور والكاميرا
import time                    # الوقت (sleep, الـ cooldown, الـ FPS)
import threading               # عشان الـ GPS يشتغل في thread منفصل
import json                    # (مش مستخدم كتير هنا، بس متاح)
import os                      # المسارات والملفات
import sys                     # sys.exit للخروج عند خطأ
import uuid                    # توليد device_id من الـ MAC address
import wave                    # كتابة ملفات صوت WAV (البيب)
import struct                  # تحويل أرقام لـ bytes (للصوت)
from collections import deque  # طابور سريع للـ confirmation buffer
from datetime import datetime, timezone  # الـ timestamps بصيغة UTC
import requests                # بعت HTTP requests للسيرفر
import numpy as np             # عمليات الأرقام/المصفوفات (الصور والصوت)
```

**سؤال متوقع:** إيه الفرق بين `import x` و `from x import y`؟
- `import cv2` → بتستخدمه كده: `cv2.imshow(...)`.
- `from datetime import datetime` → بتستخدم `datetime` على طول من غير `datetime.datetime`.

### 5.2 الإعدادات (CONFIGURATION) — الأسطر 22–80

#### اختيار الموديل (22–37)
```python
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))  # مسار فولدر السكريبت
NCNN_MODEL = os.path.join(SCRIPT_DIR, "best_ncnn_model")  # الموديل السريع
PT_MODEL = next(... "best_yolo11.pt" ... "best.pt" ...)   # البديل
MODEL_PATH = NCNN_MODEL if os.path.isdir(NCNN_MODEL) else PT_MODEL
```
- `__file__` = مسار الملف نفسه. `os.path.abspath` بيحوّله لمسار كامل، و`dirname` بياخد الفولدر.
- **ليه نستخدم المسار النسبي ده؟** عشان السكريبت يشتغل من أي مكان من غير ما نكتب مسارات ثابتة (hardcoded) تتكسر لو نقلنا المشروع.
- **المنطق:** لو فولدر `best_ncnn_model` موجود → استخدمه (أسرع 3–4 مرات على الراسبري). لو مش موجود → استخدم ملف `.pt`.
- البديل (`PT_MODEL`) بيفضّل `best_yolo11.pt` (نفس الموديل اللي اتعمل منه الـ NCNN) قبل `best.pt` القديم.

#### الـ Confidence Tiers (39–53) — **أهم جزء، ركّز هنا**
```python
CONFIDENCE_THRESHOLD   = 0.55  # الأرضية المطلقة — تحتها يتجاهل تماماً
MEDIUM_CONFIDENCE      = 0.60  # [0.60, 0.75) = "ممكن" → محتاج تأكيد
HIGH_CONFIDENCE        = 0.75  # >= كده → frame واحد يكفي للتسجيل فوراً
CONFIRM_FRAMES         = 2     # كام frame متوسط الثقة عشان نأكّد
CONFIRM_WINDOW_SECONDS = 1.0   # لازم الـ frames دي تيجي في خلال ثانية
YOLO_CONF = 0.5                # العتبة الداخلية لـ YOLO
```

**القصة وراء ده (مهمة جداً للمناقشة):**
في الاختبار الحقيقي، الموديل كتب إن **رسمة على تيشيرت** مطب، بنسبة ثقة 0.50–0.51. لكن المطبات الحقيقية بتطلع **0.80+**. يعني في **فجوة واضحة** بين الصح والغلط. النظام ده بيستغل الفجوة دي.

#### إعدادات تانية (55–80)
```python
PROCESS_EVERY_N_FRAMES = 2   # نعالج frame من كل 2 (نخفّف الحمل)
BUMP_COOLDOWN_SECONDS = 3    # بعد ما نسجّل مطب، نستنى 3 ثواني
ENABLE_DISPLAY = False       # headless = من غير شاشة (العربية مفيهاش مونيتور)
API_URL = "http://127.0.0.1:8000"  # عنوان السيرفر (نفس الجهاز)
CAMERA_WIDTH = 1280; CAMERA_HEIGHT = 960  # دقة الكاميرا (FOV واسع)
EGYPT_LAT_MIN/MAX, EGYPT_LON_MIN/MAX  # حدود مصر (للتحقق من الـ GPS)
DEDUP_RADIUS_METERS = 8      # المطبات في نطاق 8 متر = نفس المطب
```
- **`PROCESS_EVERY_N_FRAMES = 2`:** الراسبري مش قادر يعمل YOLO على كل frame (هيبطّأ). فبنعالج نُص الـ frames بس. ده trade-off بين السرعة والدقة.
- **`BUMP_COOLDOWN_SECONDS = 3`:** المطب الواحد بيفضل في الصورة كذا frame. من غير cooldown هنسجّله 10 مرات. الـ cooldown بيقول "بعد ما سجّلت مطب، تجاهل أي مطب جديد لمدة 3 ثواني".
- **حدود مصر:** لو الـ GPS رجّع إحداثيات بره مصر (غلط) أو (0,0) → نرفضها.

### 5.3 الـ Geo Utils (الأسطر 83–113)

#### `is_valid_egypt_location(lat, lon)` (84)
بيرفض قراءات الـ GPS الواضح إنها غلط:
```python
if lat is None or lon is None: return False   # مفيش قراءة
if lat == 0.0 or lon == 0.0:   return False   # (0,0) = الـ GPS لسه مش جاهز
if not (22.0 <= lat <= 32.0):  return False   # بره خطوط عرض مصر
if not (25.0 <= lon <= 37.0):  return False   # بره خطوط طول مصر
return True
```
**ليه؟** أول ما الـ GPS يشتغل وقبل ما يلاقي أقمار، بيرجّع (0,0) أو أرقام عشوائية. لو سجّلنا مطب على (0,0) ده في وسط المحيط الأطلسي! فالفلتر ده بيحمينا.

#### `haversine_distance(lat1, lon1, lat2, lon2)` (97) — **سؤال شائع**
بيحسب المسافة بالمتر بين نقطتين GPS على سطح الأرض (الكروي).
```python
R = 6371000  # نصف قطر الأرض بالمتر
# معادلة Haversine: بتحسب "المسافة على القوس" (great-circle distance)
a = sin²(Δφ/2) + cos(φ1)·cos(φ2)·sin²(Δλ/2)
distance = R · 2 · atan2(√a, √(1−a))
```
**ليه مش نستخدم نظرية فيثاغورس العادية؟** لأن الأرض **كروية** مش مسطّحة. على مسافات صغيرة الفرق بسيط، بس Haversine هي الطريقة الصح للمسافات على كرة. (`φ` = latitude، `λ` = longitude، بالراديان).

#### `is_near_recorded_bump(...)` (108)
بيلف على المطبات اللي سجّلناها في الجلسة دي، ولو لقى واحد في نطاق 8 متر → بيرجّع `True` (يعني "ده متسجّل قبل كده، تجاهله").

### 5.4 نظام الـ Tiering — `evaluate_detection()` (الأسطر 117–147) ⭐

ده العقل اللي بيقرر "ده مطب حقيقي ولا لأ". بياخد:
- `highest_conf`: أعلى نسبة ثقة في الـ frame ده.
- `medium_buffer`: طابور (deque) فيه توقيتات آخر كشوفات "متوسطة الثقة".
- `now`: الوقت الحالي.

```python
if highest_conf >= HIGH_CONFIDENCE:        # 0.75+
    medium_buffer.clear()
    return True, "[HIGH]"                   # سجّل فوراً، من غير تأخير
```
**المنطق:** المطب الواضح (0.80+) لازم يتسجّل فوراً من frame واحد. ده اللي بيحمينا وإحنا بنسوق بسرعة — لأن المطب بيفضل في الصورة ~0.7 ثانية بس.

```python
if highest_conf >= MEDIUM_CONFIDENCE:       # بين 0.60 و 0.75
    medium_buffer.append(now)               # ضيف الوقت ده للطابور
    cutoff = now - CONFIRM_WINDOW_SECONDS    # أي حاجة أقدم من ثانية
    while medium_buffer and medium_buffer[0] < cutoff:
        medium_buffer.popleft()             # امسح القديم
    if len(medium_buffer) >= CONFIRM_FRAMES: # بقى عندنا 2 في خلال ثانية؟
        medium_buffer.clear()
        return True, f"[CONFIRMED x{n}]"     # أكّدنا → سجّل
```
**المنطق:** الكشف "المشكوك فيه" (0.60–0.75) محتاج يتأكّد بـ frame تاني في خلال ثانية. ده بيشيل الكشوفات الوميض (flickery) اللي بتظهر وتختفي بسرعة — دي غالباً false positives.

```python
return False, ""   # تحت 0.60 → مش مطب
```

**ليه `deque` مش `list`؟** الـ `deque` بيشيل من الأول (`popleft`) بسرعة O(1)، الـ list بيكون بطيء O(n). وكمان الطابور **محدود بالوقت** — بيمسح القديم باستمرار → **مفيش memory leak**.

**جدول التلخيص (احفظه):**

| نسبة الثقة | القرار |
|-----------|--------|
| `< 0.55` | يتجاهل تماماً (دي الـ false positives زي التيشيرت) |
| `0.55 – 0.60` | noise band — يتجاهل، مبيعدّش في التأكيد |
| `0.60 – 0.75` | محتاج 2 frames في ثانية → `[CONFIRMED]` |
| `>= 0.75` | تسجيل فوري → `[HIGH]` |

### 5.5 الـ Device ID — `get_or_create_device_id()` (151)
```python
device_id = f"pi_{uuid.getnode():012x}"   # من الـ MAC address
```
- بيولّد ID ثابت للجهاز ويحفظه في `device_id.txt`. أول مرة بيعمله، وبعد كده بيقراه من الملف.
- `uuid.getnode()` بيرجّع الـ MAC address (رقم الكارت الشبكة الفريد). `:012x` بيحوّله لـ hex بـ 12 خانة.
- **ليه؟** عشان السيرفر يعرف كل مطب اتبلّغ من أنهي جهاز → ده بيمكّن ميزة "كام جهاز أكّد المطب ده" (`min_confirmations`).

### 5.6 الصوت — `class AudioFeedback` (164)
بيعمل صوت "بيب" لما يحصل حاجة (عشان السواق مش بيبص على الشاشة).
- `__init__`: بيشغّل pygame mixer. لو مفيش كارت صوت → بيكمّل من غير صوت (graceful — ميقعش).
- `_generate_sounds()`: بيولّد ملفات WAV **برمجياً** لو مش موجودة (مش محتاجين ملفات جاهزة).
- `_create_wav()`: بيكتب موجة جيبية (sine wave) — `value = amplitude · 32767 · sin(2π·f·t)`. الـ `fade in/out` عشان الصوت ميطلعش "طقة".
- `play_success()`: بيب واحدة (مطب اتسجّل ✅).
- `play_warning()`: بيب مرتين (مطب اتكشف بس مفيش GPS ⚠️).

**ليه `try/except` في كل مكان؟** عشان الصوت مش حاجة حرجة — لو فشل، النظام لازم يكمّل شغل عادي. ده مبدأ "fail gracefully".

### 5.7 الـ GPS في Thread — `class GPSReader` (246) ⭐

**المشكلة:** قراءة الـ GPS **بتعطّل (blocking)** — ممكن تستنى لما القراءة تيجي. لو عملناها في اللوب الرئيسي، الكاميرا هتقف تستنى الـ GPS. الحل: **thread منفصل**.

```python
def _connect(self):
    import gps as gps_module
    self.session = gps_module.gps(mode=WATCH_ENABLE | WATCH_NEWSTYLE)  # اتصل بـ gpsd
    self._thread = threading.Thread(target=self._read_loop, daemon=True)
    self._thread.start()  # شغّل القراءة في الخلفية
```
- `daemon=True` → الـ thread ده بيموت تلقائياً لما البرنامج الرئيسي يقفل.

```python
def _read_loop(self):   # بيشتغل في الخلفية طول الوقت
    while self._running:
        report = self.session.next()        # استنى قراءة من gpsd
        if report['class'] == 'TPV':         # TPV = Time-Position-Velocity
            lat, lon = report.lat, report.lon
            if is_valid_egypt_location(lat, lon):
                with self._lock:             # قفل عشان الـ thread safety
                    self.latitude = lat; self.longitude = lon
                    self.has_fix = True
```
- **`with self._lock`:** ده **mutex**. اللوب الرئيسي ممكن يقرأ `latitude` في نفس اللحظة اللي الـ thread بيكتب فيها → ده ممكن يدّي قراءة نص ونص. الـ lock بيمنع ده — واحد بس يدخل في المرة.

```python
def get_location(self):
    with self._lock:
        if not self.has_fix: return None
        return {'latitude':..., 'longitude':..., 'altitude':..., 'timestamp':...}
```
- بيرجّع آخر إحداثيات معروفة، أو `None` لو لسه مفيش fix.

```python
def wait_for_fix(self, timeout=60):   # في البداية، استنى لحد ما الـ GPS يلاقي أقمار
```
- بيستنى لحد ما الـ GPS يجهز (بحد أقصى timeout). لو معرفش، بيكمّل ويفضل يحاول في الخلفية.

**مصطلح:** "GPS fix" = إن الجهاز لقى أقمار صناعية كفاية (3+) عشان يحدد مكانه. أول تشغيل في مكان مفتوح بياخد 30 ثانية لدقايق.

### 5.8 الكاميرا — `class PiCameraCapture` (335) + `open_camera()` (374)

#### `PiCameraCapture` — الـ wrapper
بيخلّي `picamera2` تتصرّف زي `cv2.VideoCapture` العادية (بـ `.read()` و `.release()`).

```python
config = self.picam2.create_preview_configuration(
    main={"size": (width, height), "format": "RGB888"}
)
```
⭐ **أهم سطر في موضوع الألوان (سؤال متوقع):**
أسماء الـ formats في picamera2 **معكوسة** عن ترتيب الـ channels الفعلي:
- `format="RGB888"` → بيرجّع مصفوفة بترتيب **B, G, R** (يعني BGR ✅)
- `format="BGR888"` → بيرجّع **R, G, B** (يعني RGB ❌)

OpenCV و YOLO **الاتنين عايزين BGR**. فبنطلب `"RGB888"` عشان ناخد BGR على طول. لو استخدمنا `"BGR888"` غلط، الأحمر والأزرق بيتبدلوا (الوش بيطلع أزرق) وكمان YOLO بياخد ألوان مقلوبة فدقته بتقل.

#### `open_camera()` — 3 طرق احتياطية
بيجرّب 3 طرق بالترتيب:
1. **picamera2** (الطريقة الأساسية على Pi 5 Trixie).
2. **OpenCV V4L2** (احتياطي).
3. **OpenCV default** (احتياطي تاني).

**ليه 3 طرق؟** المتانة (robustness). لو طريقة فشلت، يجرّب اللي بعدها بدل ما البرنامج يقع. كل طريقة بتتأكد إنها قدرت تقرأ frame فعلاً قبل ما تعتمدها.

### 5.9 التواصل مع السيرفر (419–446)

#### `report_to_api(location, confidence, device_id)` (420)
```python
data = {"latitude":..., "longitude":..., "confidence":..., "timestamp":...,
        "altitude":..., "device_id":...}
response = requests.post(f"{API_URL}/report_bump", json=data, timeout=2)
return True, result.get("status", ...)   # status = "new" أو "merged"
```
- بيبعت المطب للسيرفر كـ JSON عبر HTTP POST. `timeout=2` عشان لو السيرفر بطيء، مايعطّلش الكشف.
- بيرجّع `(نجح؟, الحالة)` — الحالة "merged" يعني المطب كان معروف قبل كده.

#### `check_api_server()` (440)
بيتأكد إن السيرفر شغّال قبل ما نبدأ (GET على `/`).

### 5.10 الـ main() — اللوب الرئيسي (450) ⭐⭐

ده اللي بيربط كل حاجة. الترتيب:

**أولاً، التجهيز (450–504):**
```python
DEVICE_ID = get_or_create_device_id()   # ID الجهاز
# طباعة بانر فيه معلومات النظام
if not os.path.exists(MODEL_PATH): sys.exit(1)   # تأكد الموديل موجود
api_available = check_api_server()       # تأكد السيرفر شغّال
model = YOLO(MODEL_PATH, task="detect")  # حمّل الموديل
audio = AudioFeedback(...)               # جهّز الصوت
gps = GPSReader(); gps.wait_for_fix(30)  # جهّز الـ GPS واستنى fix
cap = open_camera()                      # افتح الكاميرا
```
- `task="detect"`: لازمة للـ NCNN عشان مايطلعش warning (الـ NCNN مفيهوش معلومة نوع المهمة).

**المتغيّرات قبل اللوب (506–520):**
```python
frame_counter, bump_count, merge_count = 0, 0, 0
recorded_locations = []     # المطبات اللي سجّلناها (للـ dedup المحلي)
last_bump_time = 0          # وقت آخر مطب (للـ cooldown)
medium_buffer = deque()     # طابور التأكيد
last_heartbeat = time.time()
```

**اللوب نفسه (524–624):**
```python
while True:
    ret, frame = cap.read()           # اقرأ frame
    if not ret: continue              # لو فشل، كمّل

    frame_counter += 1
    # حساب الـ FPS كل 30 frame

    if frame_counter % PROCESS_EVERY_N_FRAMES != 0:
        continue                      # تخطّى الـ frames اللي مش هنعالجها

    results = model(frame, conf=YOLO_CONF, verbose=False)   # شغّل YOLO
    highest_conf = max(... boxes ..., default=0.0)          # أعلى ثقة

    should_record, detection_tag = evaluate_detection(highest_conf, medium_buffer, now)

    if should_record and (now - last_bump_time > BUMP_COOLDOWN_SECONDS):
        location = gps.get_location()
        if location is None:                    # مفيش GPS
            audio.play_warning()                # بيب تحذير
            last_bump_time = now
        else:
            if is_near_recorded_bump(...):      # سجّلناه قبل كده؟
                last_bump_time = now            # تجاهل بصمت
            else:
                recorded_locations.append((lat, lon))
                report_to_api(...)              # ابعت للسيرفر
                audio.play_success()            # بيب نجاح
                print(f"[BUMP #{total}] ...")
```

**ترتيب الشروط مهم (سؤال متوقع):**
1. هل ده مطب أصلاً؟ (`should_record` من الـ tiering)
2. هل عدّى الـ cooldown؟ (مش هنكرر نفس المطب)
3. هل في GPS؟ (مطب من غير إحداثيات = بلا قيمة)
4. هل ده مكان جديد؟ (dedup محلي)
5. → سجّل وابعت.

**الـ Display / Heartbeat (606–624):**
- لو `ENABLE_DISPLAY=True`: يعرض الصورة بالمربعات (`results[0].plot()`).
- لو headless: ينام 5 ملي ثانية، ويطبع سطر `[ALIVE]` كل 5 ثواني عشان نعرف إنه شغّال (مش معلّق).

**التنظيف (626–649):**
```python
finally:                          # بيشتغل دايماً، حتى لو حصل crash
    cap.release()                 # سيب الكاميرا
    gps.close()                   # اقفل الـ GPS
```
- **ليه `finally`؟** عشان لو حصل أي خطأ، الكاميرا والـ GPS لازم يتسيبوا. لو سبنا الكاميرا "مقفولة" هنحتاج نعمل reboot للراسبري.
- بعدها بيطبع ملخص الجلسة (كام مطب جديد، كام مدموج، إلخ).

---

## 6. كود السيرفر — `api_server.py`

سيرفر بسيط بـ **FastAPI** بيستقبل المطبات ويخزّنها في ملف JSON.

### 6.1 الـ Imports والإعدادات (13–37)
```python
from fastapi import FastAPI               # الـ framework
from fastapi.middleware.cors import CORSMiddleware  # عشان الموبايل يقدر يتصل
from pydantic import BaseModel            # التحقق من البيانات
import tempfile, threading                # للكتابة الآمنة والـ lock
import uvicorn                            # السيرفر اللي بيشغّل FastAPI

BUMPS_FILE = os.path.join(SCRIPT_DIR, "bumps_data.json")  # ملف التخزين
_write_lock = threading.Lock()           # قفل للكتابة الآمنة
DEDUP_RADIUS_METERS = 8                   # نفس الرقم اللي في الراسبري
```

### 6.2 الـ Data Model — `class BumpReport` (40) ⭐
```python
class BumpReport(BaseModel):
    latitude: float
    longitude: float
    confidence: float
    timestamp: Optional[str] = None
    altitude: Optional[float] = None
    device_id: Optional[str] = None
```
- ده بيعرّف **شكل البيانات** اللي السيرفر بيستقبلها. FastAPI/Pydantic بيتحقق تلقائياً: لو حد بعت request من غير `latitude` أو بعت نص بدل رقم → بيرجّع خطأ 422 تلقائياً.
- `Optional[...] = None` يعني الحقل ده اختياري.
- **سؤال متوقع:** ده مثال على **input validation** — حماية مهمة في أي API.

### 6.3 الـ Geo Utils (50–72)
- `haversine_distance(...)`: نفس المعادلة اللي في الراسبري (المسافة بين نقطتين).
- `find_nearby_bump(bumps, lat, lon)`: بيلف على كل المطبات المخزّنة، ولو لقى واحد في نطاق 8 متر بيرجّع `(index, bump)`، وإلا `(None, None)`.

### 6.4 الـ CORS (78–84)
```python
app.add_middleware(CORSMiddleware, allow_origins=["*"], ...)
```
- **CORS** = Cross-Origin Resource Sharing. بدونه، تطبيق الموبايل/المتصفح هيرفض يتصل بالسيرفر لأنهم على "origins" مختلفة. `allow_origins=["*"]` يعني "اسمح للكل".
- **ملاحظة أمنية للمناقشة:** `*` مريح للتطوير، بس في الإنتاج الحقيقي يُفضّل تحديد origins معيّنة.

### 6.5 التخزين — `load_bumps()` و `save_bumps()` (88–117) ⭐

#### `load_bumps()` (88)
```python
if not os.path.exists(BUMPS_FILE): return []
try:
    return json.load(f)
except (json.JSONDecodeError, IOError):
    return []   # لو الملف تالف، ابدأ من قايمة فاضية بدل ما تقع
```

#### `save_bumps()` (98) — **الكتابة الذرّية (Atomic Write)** ⭐
```python
fd, tmp_path = tempfile.mkstemp(...)     # اكتب في ملف مؤقت الأول
with os.fdopen(fd, 'w') as f:
    json.dump(bumps, f, indent=2)
    f.flush(); os.fsync(f.fileno())      # اتأكد اتكتب على الديسك فعلاً
os.replace(tmp_path, BUMPS_FILE)         # استبدل الملف الأصلي (عملية ذرية)
```
- **المشكلة اللي بيحلها:** لو كتبنا على الملف مباشرة وحصل قطع كهربا في النص → الملف يتلف وكل البيانات تضيع.
- **الحل:** نكتب في ملف مؤقت، وبعد ما نتأكد إنه اتكتب كامل، نعمل `os.replace` — دي عملية **atomic** على Linux (يا بتحصل كاملة يا متحصلش خالص). فالملف الأصلي إما القديم السليم أو الجديد السليم — **مستحيل يبقى نص ونص**.
- مهم جداً عشان وقت المناقشة لو حصل أي حاجة، قاعدة البيانات متضيعش.

### 6.6 الـ Endpoints (الـ Routes)

#### `GET /` (121) — فحص الحالة
بيرجّع معلومات السيرفر (عدد المطبات، الحالة "running"). الراسبري بيستخدمه في `check_api_server()`.

#### `POST /report_bump` (133) ⭐⭐ — أهم endpoint
```python
with _write_lock:                        # قفل: واحد بس يكتب في المرة
    bumps = load_bumps()
    idx, existing = find_nearby_bump(bumps, lat, lon)   # في مطب قريب؟

    if existing is not None:              # آه → ادمج
        existing["reports_count"] += 1
        existing["confidence"] = max(existing["confidence"], new_conf)
        reporters = set(existing["reported_by"]); reporters.add(device_id)
        existing["reported_by"] = sorted(reporters)
        save_bumps(bumps)
        return {"status": "merged", ...}

    else:                                # لأ → مطب جديد
        bump_id = f"bump_{len(bumps):04d}"   # zero-padded: bump_0000
        bump_data = {"id":..., "lat":..., "reports_count":1, "reported_by":[device_id], ...}
        bumps.append(bump_data)
        save_bumps(bumps)
        return {"status": "success", ...}
```

**الفكرة (deduplication على مستوى السيرفر):**
- لو جه مطب في نطاق 8 متر من مطب موجود → **بنحدّثه مش بنكرره**:
  - نزوّد `reports_count` (كام مرة اتبلّغ).
  - ناخد أعلى `confidence`.
  - نضيف الجهاز لـ `reported_by` (لو جهاز جديد) — `set` عشان منكررش نفس الجهاز.
- لو مفيش مطب قريب → نضيف مطب جديد بـ ID متسلسل.

**ليه `with _write_lock`؟** (سؤال متوقع جداً)
FastAPI بيشغّل الـ endpoints في **threadpool**، يعني ممكن request اتنين يوصلوا في نفس اللحظة. من غير القفل:
- request A يقرأ القايمة، request B يقرأ نفس القايمة، الاتنين يضيفوا، واحد بس يتكتب → **بيانات تضيع**.
- أو الاتنين ميلاقوش بعض قريبين → **مطب مكرر**.

الـ lock بيخلّي عملية القراءة-التعديل-الكتابة كلها تحصل لـ request واحد بس في المرة. ده اسمه **critical section**.

#### `GET /get_bumps` (195) — الموبايل بيستخدمه
```python
def get_bumps(limit: int = 100, min_confirmations: int = 1):
    bumps = load_bumps()
    if min_confirmations > 1:
        bumps = [b for b in bumps if len(b["reported_by"]) >= min_confirmations]
    return {"total":..., "bumps": bumps[-limit:]}
```
- بيرجّع المطبات. الـ query params:
  - `limit`: أقصى عدد (افتراضي 100).
  - `min_confirmations`: يرجّع بس المطبات اللي أكّدها عدد أجهزة ≥ الرقم ده.
- **الفكرة (crowdsourcing):** مطب أكّدته 5 عربيات = موثوق أكتر من مطب عربية واحدة شافته (ممكن يكون false positive). `min_confirmations=2` بيفلتر الكشوفات الفردية المشكوك فيها.

#### `DELETE /clear_bumps` (221) — للاختبار بس
بيمسح كل المطبات (تحت الـ lock). مفيد لتنضيف قاعدة البيانات قبل عرض جديد.

### 6.7 `start_server()` (230) و `__main__` (246)
```python
def start_server(host, port, background=False):
    config = uvicorn.Config(app, host=host, port=port)
    server = uvicorn.Server(config)
    if background:                        # في thread (لـ run_laptop.py)
        thread = threading.Thread(target=server.run, daemon=True); thread.start()
        return thread
    server.run()                         # blocking (لـ python api_server.py)
```
- `host="0.0.0.0"` يعني "اقبل اتصالات من أي جهاز على الشبكة" (مش بس localhost) — عشان الموبايل يقدر يتصل.
- `background=True`: بيشغّل السيرفر في thread (نسخة اللابتوب بتستخدمه عشان تشغّل السيرفر والكشف في برنامج واحد).

---

## 7. المفاهيم اللي لازم تفهمها كويس

| المفهوم | شرح سريع |
|---------|----------|
| **YOLO** | "You Only Look Once" — موديل **object detection** بيلاقي الأشياء ومكانها (bounding box) في الصورة في مرور واحد. بنستخدم YOLO11n (الـ n = nano = أصغر وأسرع نسخة). |
| **Object Detection vs Classification** | Classification = "الصورة دي فيها مطب ولا لأ". Detection = "فيه مطب، ومكانه هنا، بثقة كذا". إحنا عايزين Detection. |
| **Confidence** | نسبة ثقة الموديل (0–1) إن ده فعلاً مطب. |
| **NCNN** | إطار عمل (framework) لتشغيل موديلات الذكاء الاصطناعي على المعالجات (CPU/ARM) من غير GPU — مُحسّن للموبايل والراسبري. حوّلنا الموديل من PyTorch (`.pt`) لـ NCNN عشان يبقى أسرع 3–4 مرات على الراسبري. |
| **Inference** | تشغيل الموديل على صورة جديدة عشان ياخد قرار (مقابل Training = تدريب الموديل). |
| **Haversine** | معادلة المسافة بين نقطتين على كرة (الأرض). |
| **Threading** | تشغيل أكتر من جزء من الكود في نفس الوقت. استخدمناه عشان الـ GPS مايعطّلش الكاميرا. |
| **Lock / Mutex** | قفل بيمنع جزئين كود يلمسوا نفس البيانات في نفس الوقت (thread safety). |
| **FastAPI / REST API** | طريقة عشان البرامج تتكلم مع بعض عبر HTTP (GET/POST). |
| **JSON** | صيغة نص لتبادل البيانات (مفهومة للإنسان والآلة). |
| **CORS** | إذن بيخلّي الموبايل/المتصفح يتصل بالسيرفر. |
| **Atomic write** | كتابة "يا كلها يا ولا حاجة" — تحمي الملف من التلف. |
| **gpsd** | برنامج خلفية بيدير الـ GPS ويوزّع قراءاته للبرامج. |
| **headless** | تشغيل من غير شاشة/واجهة رسومية. |
| **FOV** | Field Of View — زاوية الرؤية. دقة أعلى = رؤية أوسع. |

---

## 8. أسئلة المناقشة المتوقعة + الإجابات

**س: إزاي النظام بيفرّق بين مطب حقيقي و false positive؟**
ج: عن طريق نظام **tiers** للثقة. المطبات الحقيقية بتطلع 0.80+ فبتتسجّل فوراً. الـ false positives (زي رسمة تيشيرت) بتطلع ~0.50 فبتتجاهل لأنها تحت عتبة 0.55. والمنطقة الرمادية (0.60–0.75) محتاجة تأكيد من frame تاني في خلال ثانية.

**س: ليه مش خلّيت العتبة 0.75 لكل حاجة وخلصت؟**
ج: لأن بعض المطبات الحقيقية في ظروف صعبة (إضاءة، زاوية) ممكن تطلع 0.65. لو رفعت العتبة هفوّتها. الـ tiers بتديني الاتنين: حساسية للمطبات الواضحة + تأكيد للمشكوك فيه.

**س: ليه مش بتأكّد كل المطبات بـ frames كتير؟ مش هيبقى أدق؟**
ج: لأ — إحنا في **عربية بتتحرك**. على 40 كم/س المطب بيفضل في الصورة ~0.7 ثانية = 3–4 frames بس. لو طلبت تأكيد كتير، هفوّت مطبات حقيقية وإحنا ماشيين. عشان كده المطب الواضح (0.75+) بيتسجّل فوراً من frame واحد.

**س: ليه picamera2 مش OpenCV عادي للكاميرا؟**
ج: على Raspberry Pi 5 / Debian Trixie، الكاميرا بتشتغل عبر libcamera، والطريقة الرسمية ليها هي picamera2. OpenCV العادي مش بيشوف كاميرا الـ CSI مباشرة. بس عملت fallback لـ OpenCV لو picamera2 فشل.

**س: مشكلة الألوان (blue tint) كانت إيه؟**
ج: أسماء الـ formats في picamera2 معكوسة. `BGR888` بيدّي مصفوفة RGB، و`RGB888` بيدّي BGR. OpenCV عايز BGR. فاستخدمت `RGB888` عشان آخد BGR صح. استخدام `BGR888` كان بيبدّل الأحمر والأزرق (الوش يطلع أزرق) وكمان بيقلل دقة YOLO.

**س: ليه الـ GPS في thread منفصل؟**
ج: لأن قراءة الـ GPS blocking (بتستنى). لو في اللوب الرئيسي، الكاميرا هتقف تستنى. الـ thread بيخلّي الـ GPS يقرأ في الخلفية واللوب الرئيسي ياخد آخر إحداثية متاحة فوراً.

**س: ليه فيه dedup مرتين (راسبري + سيرفر)؟**
ج: الراسبري بيمنع نفس الجهاز يبعت نفس المطب مرات كتير في نفس الجلسة (يخفّف الشبكة). السيرفر بيدمج المطبات من **كل الأجهزة** (عربيتين مختلفتين عدّوا على نفس المطب = مطب واحد بتأكيدين).

**س: ليه ملف JSON مش قاعدة بيانات (database)؟**
ج: لبساطة المشروع وحجم البيانات الصغير. JSON كفاية وسهل التصحيح والقراءة. لو النظام كبر (آلاف المطبات / استعلامات كتير)، نتحوّل لـ SQLite أو PostgreSQL. عملت الكتابة atomic عشان أحمي الملف من التلف.

**س: إيه الـ cooldown وليه 3 ثواني؟**
ج: المطب الواحد بيظهر في كذا frame متتالي. من غير cooldown هسجّله 10 مرات. الـ cooldown بيقول "بعد ما سجّلت مطب، تجاهل لمدة 3 ثواني" — وقت كافي عشان العربية تعدّي المطب.

**س: ليه بتعالج frame من كل 2 مش كلهم؟**
ج: الراسبري CPU محدود. تشغيل YOLO على كل frame هيخلّي الـ FPS واطي جداً. معالجة نُص الـ frames بتوازن بين السرعة والدقة — ولسه بكشف المطب لأنه بيفضل لكذا frame.

**س: إزاي ضمنت إن السيرفر مايتعطلش لو request اتنين جم مع بعض؟**
ج: استخدمت `threading.Lock` حوالين عملية القراءة-التعديل-الكتابة (critical section)، وكمان الكتابة atomic (`os.replace`). فمستحيل request يقرأ ملف نص-مكتوب أو إن اتنين يكتبوا فوق بعض.

**س: لو الـ GPS مش لاقي إشارة بيحصل إيه؟**
ج: المطب **مش بيتسجّل** (مطب من غير إحداثيات بلا قيمة)، وبيطلع صوت تحذير (بيب مرتين) عشان أعرف. لما الإشارة ترجع، بيشتغل عادي.

**س: ليه YOLO11n (nano) مش نسخة أكبر؟**
ج: لأنه بيشتغل على الراسبري (CPU محدود) لازم real-time. النسخة الـ nano أصغر وأسرع، ودقتها كفاية لمهمة "مطب / مش مطب" (class واحدة).

**س: إيه أكبر تحدي واجهك؟**
ج: (إجابة شخصية — مثال) موازنة السرعة والدقة على جهاز محدود وعربية بتتحرك: لازم أكشف المطب في أقل من ثانية من غير false positives. حليتها بـ NCNN (سرعة) + نظام الـ tiers (دقة من غير تأخير).

---

> **نصيحة أخيرة للمذاكرة:** افتح الملفين جنب الدليل ده، واقرأ كل فانكشن في الكود وبعدين اقرأ شرحها هنا. وجرّب تشرح "رحلة الـ bump" (قسم 3) بصوت عالي من غير ما تبص — لو قدرت، انت جاهز. 💪

</div>
