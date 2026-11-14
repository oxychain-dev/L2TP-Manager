# GUIDE.md — راهنمای فارسی مدیریت سرور L2TP Manager

> **مبنای این راهنما:** کد شاخهٔ `development` در تاریخ ۲۰۲۶/۱۱/۱۴ و شواهد ترمینال Polaris از همین دوره. GitHub محل سورس است و **خودش سرور زنده را به‌روزرسانی نمی‌کند**.
>
> **محدودیت امنیتی:** L2TPv2/PPP بدون IPsec یا MPPE رمزنگاری ندارد؛ CHAP فقط نام کاربری/رمز PPP را احراز می‌کند و محرمانگی ترافیک را تأمین نمی‌کند. انتخاب «PSK Offered» صرفاً نمایش اطلاعات کلید **مشترک** است، نه ساخت کلید اختصاصی و نه اجبار IPsec برای آن حساب.

## ۱. اجزای سیستم و مرز مسئولیت‌ها

| جزء | نقش | اثر یا محدودیت |
| --- | --- | --- |
| `xl2tpd.service` + `pppd` | L2TPv2 روی UDP 1701 و احراز هویت CHAP | کاربران ساده و کاربران دارای IPsec از مرحلهٔ PPP مشترک استفاده می‌کنند |
| `strongswan.service` / `charon-systemd` | **اختیاری**: IKEv1/PSK + ESP transport برای کلاینت‌های سازگار | UDP 500/4500؛ PSK سراسری، نه وابسته به Username PPP |
| `l2tp-forwards.service` | Forwardهای پروژه | اجرای مستقیم `l2tp-manager.sh start-forwards` از Worktree نصب‌شده؛ تغییر سورس روی سرویس بعد از Restart اثر می‌گذارد |
| `l2tp-direct6.timer` و ابزار reconcile | مسیرهای IPv6 مستقیم برای کاربران انتخابی | نباید با شمارهٔ متغیر `pppN` اشتباه گرفته شود |
| سرویس‌های GRE / WARP / Docker | مسیرها و خروجی‌های مستقل | تغییر بی‌برنامهٔ Routing/NAT/Firewall می‌تواند آن‌ها را مختل کند |
| `/etc/ppp/chap-secrets` | هویت و رمز PPP + IP ثابت | خصوصی است؛ محتوایش را در Issue/چت/لاگ قرار ندهید |
| `/etc/l2tp-manager/global-psk.secrets` | کلید مشترک سراسری | فقط در ترمینال خصوصی و در صورت ضرورت نمایش داده شود |
| `/etc/l2tp-manager/psk-client-flags.json` | وضعیت «نمایش PSK» به هر حساب | **کنترل دسترسی شبکه یا ابطال کلید نیست** |
| `/etc/swanctl/conf.d/50-mobile-l2tp-ipsec.conf` | اتصال فعال IKEv1 | PSK این فایل باید با فایل سراسری هماهنگ باشد |

برای آشنایی با معماری چند-WAN و محدودیت‌های تست زنده، [راهنمای Plain L2TP Multi-WAN](docs/PLAIN-L2TP-MULTIWAN.md) را بخوانید. طرح سامانهٔ آیندهٔ داشبورد و Subscription در [FUTURE-SELF-SERVICE](docs/FUTURE-SELF-SERVICE.md) است و **هنوز پیاده‌سازی نشده**.

## ۲. اولین ورود: تشخیص نسخه و محیط (بدون تغییر)

از SSH یا کنسول مطمئن VPS وارد شوید. کاربر باید برای بررسی‌های مدیریتی مجوز root/sudo داشته باشد.

~~~bash
(
  set -eu
  repo=$(git rev-parse --show-toplevel)
  printf 'Repository: %s\n' "$repo"
  git -C "$repo" status --short
  git -C "$repo" rev-parse HEAD
  echo "=== Service state ==="
  systemctl is-active xl2tpd strongswan l2tp-direct6.timer || true
  echo "=== Boot settings ==="
  systemctl is-enabled xl2tpd strongswan l2tp-direct6.timer || true
  echo "=== Listening UDP ports ==="
  sudo ss -H -lunp | grep -E ':(1701|500|4500)[[:space:]]' || true
  echo "=== PPP interfaces ==="
  ip -br -4 addr show | grep -E '^ppp[0-9]+' || true
  echo "=== Kernel IPsec SA count ==="
  sudo ip xfrm state count
)
~~~

**تفسیر:** `active` بودن سرویس و وجود Listener تنها «آماده‌بودن پاسخ‌دهنده» را نشان می‌دهد. موفقیت اتصال IPsec به `ESTABLISHED IKE_SA`، `INSTALLED CHILD_SA`، PPP متناظر و آزمایش اینترنت روی دستگاه نیاز دارد. اگر IPsec SA صفر باشد ولی PPP کار کند، آن PPP ممکن است **Plain L2TP** باشد. نبودن جدول IPv4 شماره ۲۲۰ به‌تنهایی خطای VPN نیست؛ ابتدا Ruleهایی که به آن ارجاع می‌دهند را بررسی کنید.

### مراقبت از نسخهٔ زنده

در Polaris قبلاً مشخص شد `l2tp-forwards.service` از مخزن `/home/master/L2TP-Manager` اجرا می‌شود. وجود یک Checkout آزمایشی مجزا مانند `/home/master/L2TP-Manager-phase1-review` به معنی نصب آن روی سرویس نیست.

**ممنوع در ساعات فعالیت کاربران:** اجرای کورکورانهٔ `git pull`، `git reset --hard`، `git switch`، نصب مجدد سرور، Restart هم‌زمان سرویس‌ها، `iptables-restore` سراسری یا Flush کردن Routing/Firewall. ابتدا وابستگی `ExecStart` را بررسی کرده و با Backup و دسترسی کنسول اضطراری، تغییر را برنامه‌ریزی کنید.

## ۳. اجرای منوی مدیر

در Checkout انتخاب‌شده و **بعد از کنترل مسیر و Commit**:

~~~bash
(
  repo=$(git rev-parse --show-toplevel) || exit 1
  [ -f "$repo/l2tp-manager.sh" ] || exit 1
  sudo bash "$repo/l2tp-manager.sh"
)
~~~

منوی اصلی در سورس فعلی گزینه‌های زیر را دارد:

| گزینه | عملکرد | راهنمای ایمنی |
| --- | --- | --- |
| `1` | نصب و پیکربندی L2TP | **فقط نصب اولیه**؛ روی Polaris موجود تکرار نکنید |
| `2` | وضعیت و عیب‌یابی عمومی | گزارش، نه تضمین سلامت اینترنت مشتری |
| `3` | حذف نصب | پرخطر، مناسب حذف برنامه‌ریزی‌شده |
| `4` | افزودن PPP User (تصادفی یا دستی) | IP ثابت از تخصیص‌دهنده؛ انتخاب اختیاری ارائهٔ PSK |
| `5` | حذف حساب‌های PPP | مسیر **قدیمی و پرخطر**؛ ممکن است `xl2tpd` و Forwardها را Restart کند |
| `6` | ویرایش کاربر | تغییر رمز PPP و وضعیت ارائهٔ PSK؛ تغییر IP ثابت در فاز ۱ غیرفعال |
| `7` | لیست کاربران | Username و IP؛ رمزها مخفی؛ نمایش یک حساب با تأیید در ترمینال |
| `8` | افزودن Port Forward | فقط در صورت نیاز و پس از ممیزی دسترسی مدیریت |
| `9` | حذف Port Forward | تأثیر روی سرویس بیرونی را بررسی کنید |
| `10` | لیست Forwardها | وضعیت شبکه و پیکربندی را جداگانه تأیید کنید |
| `11` | Restart Forwardها | **ممکن است پردازش‌های socat و مسیرهای دیگر را مختل کند** |
| `12` | Start سرویس‌های L2TP/Forward | روی سرور موجود باید اثرش بررسی شود |
| `13` | Stop سرویس‌ها | باعث قطع کاربران می‌شود؛ تأیید لازم است |
| `14` | Restart سرویس‌ها | باعث قطع کاربران می‌شود؛ تأیید لازم است |
| `15` | تنظیمات Global PSK | عملیات روی تمام دارندگان PSK اثر دارد |
| `16` | مدیریت Plain L2TP Multi-WAN | برای CA2/CA3 بدون PSK و رمزنگاری، با تخصیص IP تحت Lock |
| `0` | خروج | بدون تغییر |

**پیشنهاد عملی:** اگر سرور فعال و چند کاربر آنلاین دارد، برای افزودن حساب **بدون PSK** از `16 → 4` استفاده کن؛ برای نمایش امن و تغییر PSK از `7/15`. برای حذف حساب وابسته به GRE/Direct6، ابتدا اتصال و وابستگی مسیر/Forward را قطع یا مهاجرت بده.

## ۴. مشاهدهٔ کاربران و اطلاعات قابل کپی

### لیست بدون نمایش رمزها

~~~bash
(
  repo=$(git rev-parse --show-toplevel) || exit 1
  sudo python3 "$repo/tools/psk-client-manager.py" list
  sudo python3 "$repo/tools/plain-l2tp-multiwan.py" list
  sudo python3 "$repo/tools/plain-l2tp-multiwan.py" sessions
)
~~~

`psk-client-manager.py list` وضعیت **offered / not offered** را نمایش می‌دهد. این وضعیت فقط به این معنی است که در نمایش اطلاعات اتصال، PSK نشان داده شود یا نه؛ ممکن است دارندهٔ PSK قدیمی هنوز بتواند از آن استفاده کند.

`plain-l2tp-multiwan.py sessions` اینترفیس `pppN`، Peer IPv4، شمارنده‌های RX/TX و در صورت موجودبودن Hook، Username احراز‌شده و Uptime را نمایش می‌دهد. اگر Hook نصب نباشد، Username از IP **استنباط** می‌شود؛ به‌عنوان احراز هویت قطعی استفاده نشود. `pppN` بعد از Disconnect قابل استفادهٔ مجدد است.

### نمایش اختصاصی یک کاربر در ترمینال امن

از گزینهٔ `7`، Username را وارد کنید یا از CLI به‌شکل زیر استفاده کنید:

~~~bash
(
  repo=$(git rev-parse --show-toplevel) || exit 1
  read -r -p 'Username to reveal locally: ' username
  [ -n "$username" ] || exit 1
  sudo python3 "$repo/tools/psk-client-manager.py" show --username "$username"
)
~~~

برنامه هنگام نمایش اطلاعات حساس، `REVEAL` می‌خواهد. در ترمینال خصوصی، Username، رمز PPP، IP داخلی و در صورت `offered` بودن، PSK **سراسری** نمایش داده می‌شود. اگر `Server IPv4: unverified` بود، آدرس را از پیکربندی مؤثر سرور بررسی کن؛ آن را حدس نزن.

**هرگز** متن نمایش‌داده‌شده را در Issue، تصویر عمومی، URL اشتراک، Git، لاگ یا پیام پشتیبانی کپی نکن. اطلاعات را فقط با کانال امن به صاحب حساب بده.

## ۵. افزودن حساب L2TP بدون PSK — CA2/CA3

در منوی `16`، گزینه‌های زیر موجودند:

- `1` لیست کاربران؛ `2` نشست‌های فعلی؛ `3` بررسی برخورد IP/هویت نامعلوم؛
- `4` ساخت Username و Password مستقل و گرفتن IP ثابت آزاد؛
- `5` `disable / enable / remove` حساب غیرفعال/قطع‌شده؛
- `6` سلامت `xl2tpd`، Forward و `ip_forward`.

برای افزودن حساب دوم: `16 → 4`، Username یکتا و رمز PPP ۱۲ تا ۶۴کاراکتری مجاز بده، عبارت `CREATE PLAIN ACCOUNT` را برای تأیید وارد کن. **هیچ PSK، MPPE یا IPsecی برای این حساب ایجاد یا فعال نمی‌شود.** حساب جدید IP متفاوتی از CA1 دریافت می‌کند؛ کلاینت باید واقعاً به آن متصل شود تا صحت کار مشخص شود.

این مسیر از Lock تخصیص IP، IP کاربران موجود، نشست‌های فعال، رزروها و کانفیگ‌های Direct6/GRE استفاده می‌کند؛ اگر امکان بررسی قطعی وجود نداشته باشد، باید Fail Closed شود. افزودن حساب خودکار `xl2tpd` و Forwardها را Restart نمی‌کند، اما تشخیص اثر واقعی روی نشست‌های برقرار به تست میزبان نیاز دارد.

### اتصال MikroTik به سرور

در RouterOS، هر WAN باید **L2TP Client Object** مستقل با Username اختصاصی داشته باشد. برای حساب Plain L2TP، `use-ipsec=no` و CHAP را انتخاب کن. CA1 موجود را تغییر نده؛ صرفاً ساختن CA2 به همان IP مقصد، آن را از WAN2 عبور نمی‌دهد.

برای WAN2، مسیر Underlay/VRF واقعی باید روی MikroTik بررسی شود؛ راهکار رسمی RouterOS می‌تواند `connect-to=server-address@VRF` باشد، اما فقط پس از بررسی VRF، Gateway، مسیر /32 موجود، NAT و Kill Switch. **این پروژه هیچ فرمانی را روی MikroTik اجرا نمی‌کند.**

برای هر اتصال جدید، IP داخلی PPP باید متفاوت باشد؛ اگر هدف خروجی یکسان است، باید روی **هر دو دستگاه** آدرس IPv4 عمومی واقعی سرویس خارجی را اندازه بگیری، نه صرفاً به موفقیت احراز هویت یا وجود NAT Rule اکتفا کنی.

## ۶. افزودن حساب سازگار با iPhone L2TP/IPsec

از گزینهٔ `4` برای افزودن حساب PPP استفاده کن و در مرحلهٔ ارائهٔ PSK گزینهٔ «Offer shared PSK configuration» را انتخاب کن، یا برای حساب موجود از گزینهٔ `6` استفاده کن.

تنظیمات دستی iPhone: `Type=L2TP`، `Server` برابر آدرس عمومی **تأییدشده**ٔ میزبان، `Account` برابر Username PPP، `Password` برابر رمز PPP همان حساب و `Secret` برابر PSK **مشترک و فعال**. برای iPhone الزاماً از حساب IKEv2 EAP متفاوت استفاده نکن.

وجود یک Checkbox «PSK offered» به معنی رمزنگاری اجباری نیست. **PSK سراسری است**، کلاینتِ قبلاً دارای کلید با خاموش‌کردن آن Checkbox کلید را از دست نمی‌دهد و کاربران L2TP ممکن است همچنان از مسیر بدون IPsec وارد شوند. برای `ipsec-required` واقعی، زیرساخت جداشده و تست عدم پذیرش Plain L2TP لازم است.

وضعیت واقعی iPhone در نمونهٔ Polaris در ۲۰۲۶/۱۱/۱۴: `mobile-l2tp-psk` به‌صورت `ESTABLISHED IKEv1` و `l2tp-transport` به‌صورت `INSTALLED ESP` دیده شد، با افزایش شمارنده‌های رمزنگاری و `ppp2` برای Peer قبلیِ `myiphone`. این به معنی **تأیید اینترنت IPv4/IPv6 گوشی، Username توسط PPP یا پایداری پس از Reboot نیست**.

## ۷. مدیریت Global PSK؛ بدون قطع بی‌مورد کاربران

ابتدا وضعیت و تطبیق فایل‌های موجود را بدون نمایش مقدار بررسی کن:

~~~bash
(
  repo=$(git rev-parse --show-toplevel) || exit 1
  sudo python3 "$repo/tools/psk-client-manager.py" global-status
  sudo swanctl --list-conns
  sudo swanctl --list-sas
  sudo ip xfrm state count
)
~~~

**کلید موجود را اگر اتصال موفق است، بی‌دلیل تغییر نده.** برای همگام‌سازی/چرخش در پنجرهٔ نگهداری از `15 → 2` یا `global-rotate` استفاده کن؛ ابتدا `yes`/`y`، سپس کلید جدید را در ورودی جداگانه **بدون نمایش حین تایپ** وارد و تکرار کن. Enter خالی کلید تصادفی ۱۶کاراکتری می‌سازد. ابزار کلید جدید ۸ تا ۶۴کاراکتری ASCII قابل‌چاپ را می‌پذیرد ولی فاصله، کوتیشن و بک‌اسلش را نمی‌پذیرد؛ برای امنیت کلید تصادفی ۱۶کاراکتری یا طولانی‌تر بهتر است.

این عملیات باید در نبود IKE/XFRM Session انجام شود، فایل‌های اصلی و Active/Candidate را به‌صورت کنترل‌شده هماهنگ کند، نسخهٔ پشتیبان خصوصی بسازد و با `swanctl --load-creds --clear --noprompt` اعتبارنامه‌ها را مجدداً بارگذاری کند. **همهٔ دارندگان PSK قبلی باید کلید جدید را دریافت کنند.** در صورت شکست Restore وضعیت daemon و فایل‌ها باید مستقلاً تأیید شود.

منوی `15` همچنین Reload اعتبارنامه و Restart مجزای `strongswan` یا `xl2tpd` دارد؛ Restart `xl2tpd` ممکن است تمام نشست‌های PPP را قطع کند. هشدارهای `plugin failed to load` برای افزونه‌های اختیاری strongSwan به‌تنهایی دلیل Restart یا نصب گروهی Pluginها نیست.

## ۸. ویرایش، غیرفعال‌کردن، حذف کاربران و Port Forward

- **گزینهٔ 6:** Username را انتخاب کن؛ رمز فعلی نمایش داده نمی‌شود. رمز جدید را مخفی وارد کن یا خالی بگذار، سپس انتخاب کن PSK در اطلاعات اتصال ارائه شود یا نه. تغییر رمز بر نشست جاری اثر قطعی ندارد تا کلاینت دوباره احراز هویت کند.
- **گزینهٔ 16 → 5:** `disable / enable / remove` برای حساب مشخص؛ برنامه در صورت وجود PPP Peer فعال یا وابستگی IP به Forward/Route/Direct6/GRE از تغییر پرخطر جلوگیری می‌کند. Disable یک حساب به‌تنهایی نشست قبلی را قطع نمی‌کند؛ قبل از «ابطال فوری» باید کنترل ارتباط فعال نیز پیاده‌سازی و آزمایش شود.
- **گزینهٔ 5 قدیمی:** ممکن است `xl2tpd` و سرویس Forward را Restart کند، بنابراین برای حذف یک حساب در ساعات پرترافیک توصیه نمی‌شود.
- **گزینه‌های 8 تا 11:** Port Forwardهای TCP/سرویس‌های اختصاصی. **Winbox/API یا SSH مدیریت MikroTik را به‌صورت عمومی باز نکن.** پیاده‌سازی قدیمی مدیریت Forward دارای `pkill` گسترده و بازگرداندن قواعد Firewall است؛ Restart آن را به پنجرهٔ نگهداری محدود کن.
- **اسکریپت مدیریت Route:** `l2tp-routes-manager.sh` موجود است، ولی Apply کردن همهٔ Routeهای قدیمی در بعضی مسیرها قبل از افزودن، Route فعلی را حذف می‌کند؛ روی میزبان چندکاربره بدون Snapshot و طرح Rollback اجرا نشود.

## ۹. بررسی پایداری بعد از موفقیت اتصال iPhone

### A — ممیزی فقط‌خواندنی، بدون نمایش کلیدها

~~~bash
(
  echo '=== Core services ==='
  systemctl show xl2tpd.service strongswan.service l2tp-direct6.timer \
    -p Id -p ActiveState -p UnitFileState -p Result --no-pager
  echo '=== Ancillary services ==='
  systemctl --failed --no-pager
  echo '=== Actual PPP peers ==='
  ip -br -4 addr show | grep -E '^ppp[0-9]+' || true
  echo '=== IKE/ESP sessions ==='
  sudo swanctl --list-sas
  sudo ip xfrm state count
  echo '=== Routes and rules ==='
  ip -4 rule show
  ip -6 rule show
  ip -4 route show table main
  echo '=== Private key file permissions only ==='
  sudo stat -c '%U:%G %a %n' /etc/l2tp-manager/global-psk.secrets \
    /etc/swanctl/conf.d/50-mobile-l2tp-ipsec.conf /etc/ppp/chap-secrets
)
~~~

`swanctl --list-sas` حاوی Endpointها و شناسه‌ها است؛ هنگام به‌اشتراک‌گذاری گزارش، اطلاعات شخصی کلاینت را حذف کن. **هرگز** `ip xfrm state` بدون `count` را در گزارش عمومی قرار نده؛ ممکن است کلیدهای SA را نمایش دهد.

### B — آزمون از خود دستگاه

1. در iPhone با `myiphone` اتصال L2TP/IPsec را برقرار کن.
2. مطابق لاگ باید `IKEv1 ESTABLISHED` و `ESP CHILD_SA INSTALLED` با شمارنده‌های ترافیک افزایش‌یابنده دیده شود.
3. در لاگ `pppd` یا Hook با منبع معتبر، Username احراز‌شده را با Peer PPP تطبیق بده؛ شمارهٔ `pppN` دائمی نیست.
4. روی **خود iPhone** یک وب‌سایت HTTPS IPv4 را باز کن و آدرس عمومی خروجی را با خروجی واقعی میزبان مقایسه کن. IPv6 را تنها اگر گوشی واقعاً مسیر قابل‌استفاده گرفته باشد تأیید کن.
5. قطع/وصل، تغییر Wi-Fi به Cellular، NAT-T و تلاش با PSK/Password اشتباه را در چارچوب تست کنترل‌شده بررسی کن.
6. قبل و بعد از هر آزمون، نشست‌های کاربران Plain L2TP و مسیرهای Direct6/GRE/WARP را مقایسه کن.

### C — نسخهٔ پشتیبان، Reboot و بازیابی

- قبل از هر Reboot یا Restart: دسترسی مستقل به **کنسول VPS** و امکان بازگردانی Snapshot را بررسی کن؛ اطمینان حاصل کن که قطع کاربران زمان‌بندی و پذیرفته شده است.
- Snapshot فایل‌های خصوصی را **بدون چاپ محتوا** در مسیر خصوصی Root با مجوز 0700 نگه دار؛ Backup صرفاً از فایل‌های موجود و بررسی‌شده بگیر، و در صورت نیاز روی فضای امن بیرونی نیز نگه دار.
- `systemctl is-enabled` و `systemctl is-active` همهٔ Unitهای ضروری را جداگانه بررسی کن. تنها سرویس‌هایی که عمداً نیاز به Boot دارند باید Enabled باشند. **فعال‌بودن قبلی strongSwan پس از یک Reboot مشاهده شده است، ولی آزمون بازیابی کامل گوشی بعد از همان اتصال هنوز انجام نشده است.**
- Restart سراسری یا `systemctl reboot` را بدون پنجرهٔ نگهداری برای اثبات «Stable» انجام نده. بعد از Reboot، Listenerها، IPها، Ruleها، Tunnelها، فایروال و اتصال واقعی هر کلاینت را دوباره تأیید کن.
- برای برگشت، ابتدا اثر تغییر را از لاگ/سرویس مشاهده کن، سپس فقط بخش تغییر‌داده‌شده را از Backup خصوصی Restore کن؛ Routeها و Firewall دیگران را Flush نکن.

## ۱۰. تشخیص مشکلات متداول

| علامت | علت‌های ممکن و اقدام مناسب |
| --- | --- |
| `plugin failed to load` در `swanctl` | اغلب افزونهٔ اختیاری نصب نشده؛ تا وقتی IKE/ESP با الگوریتم موردنیاز کار می‌کند، نصب/Restart کورکورانه لازم نیست |
| `NO_PROPOSAL_CHOSEN` | پروتکل/Proposal کلاینت با سرور منطبق نیست؛ در لاگ قبلی تلاش‌هایی با IKEv2 یا رمزهای قدیمی 3DES/DES رد شده‌اند؛ **رمزهای ضعیف را صرفاً برای حذف خطا فعال نکن** |
| `IKE_SAs: 0` | هنوز اتصال IPsec فعال ثبت نشده؛ Listener فعال به‌تنهایی کافی نیست |
| `SAD count 0` | هیچ SA نصب‌شده‌ای در Kernel دیده نشده؛ لزوماً شکست کاربران Plain نیست |
| `Global PSK mismatch` | فایل مدیریت سراسری با کانفیگ فعال تفاوت دارد؛ **اگر گوشی الان وصل می‌شود کلید را کورکورانه Rotate نکن**؛ در پنجرهٔ نگهداری بررسی کن |
| `Server IPv4: unverified` | ابزار نتوانسته Endpoint عمومی را از فایل و آدرس محلی تطبیق دهد؛ Endpoint مؤثر را جداگانه تأیید کن |
| `ppp0` جای `ppp2` می‌آید | شمارهٔ Interface پایدار نیست؛ Route/Policy باید به شناسه و IP واقعی کاربر متکی باشد |
| `FIB table 220 does not exist` | الزاماً خرابی نیست؛ بدون Rule/مسیر مؤثر نمی‌توان نتیجه گرفت |
| CA2 وصل می‌شود ولی WAN2 نیست | دو L2TP Client به یک IP الزاماً دو WAN نمی‌سازد؛ VRF/Route Underlay را بررسی کن |
| PPP وصل می‌شود ولی اینترنت ندارد | NAT، IPv4 forwarding، Policy Route، مسیر برگشت، DNS و Firewall را بررسی کن؛ لاگ PPP اثبات خروجی نیست |
| تغییر رمز کاربر نشست جاری را قطع نمی‌کند | تغییر برای احراز هویت بعدی است؛ ابطال فوری Session نیازمند روند جداگانه و تست‌شده است |
| `You have new mail in /var/mail/root` | ایمیل محلی Linux (Cron/سرویس/هشدار و...)؛ صرفاً عنوان، فرستنده و تاریخ را ابتدا بخوان و رمزها را افشا نکن |

## ۱۱. مرز قابلیت‌های فعلی و آینده

**موجود در سورس:** حساب PPP، وضعیت PSK مشترک، ابزار Read-only سلامت، CA2/CA3، Hook اختیاری PPP، مدیریت Serviceها و Guideهای GRE/Direct6.

**نیازمند تست زنده:** دسترسی عمومی اینترنت iPhone بعد از IPsec، تطبیق PPP Username، Reboot کامل، CA1+CA2 با WAN مستقل، یکسان‌بودن Public Egress IP، جلوگیری از اختلال هنگام حذف/Forward/PPP و امنیت فایروال.

**فقط طرح آینده، نه ویژگی آماده:** پروفایل سازگار خودکار برای `iphone|android|modem|router|all`، Backend واقعی IKEv2 برای Android جدید، محدودسازی `ipsec-required` به کاربران خاص، صفحهٔ HTML و Dashboard شخصی، دعوت یک‌بارمصرف برای ثبت‌نام و Subscription URL جداگانه/قابل ابطال برای هر کاربر.

برای پیگیری کارهای باقیمانده از [Issues مخزن](https://github.com/oxychain-dev/L2TP-Manager/issues) استفاده کن؛ هر Issue باید با معیار پذیرش و خروجی قابل‌تأیید بسته شود، نه صرفاً Pass شدن CI.
