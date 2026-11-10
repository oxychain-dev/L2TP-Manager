# برنامه اجرایی یکپارچه و وضعیت واقعی پروژه L2TP-Manager

**تاریخ ثبت شواهد:** ۲۰۲۶-۱۱-۱۰  
**دامنه:** Polaris (ورودی L2TP)، Warden (خروجی GRE)، MikroTik RouterOS، کاربران عادی و iPhone  
**مرجع کد:** فورک `oxychain-dev/L2TP-Manager`، شاخه `feature/configurable-l2tp-network` و Draft PR #1  
**قاعده وضعیت:** موفقیت یک تست مقطعی ≠ دائمی‌شدن ≠ آماده‌بودن برای همه کاربران. شواهد این گزارش خروجی‌های ارسالی اپراتور هستند، نه بررسی زنده سرورها توسط GitHub.

## ۰. هدف نهایی و مرزبندی

**هدف:** مدیریت امن و قابل‌تعمیم کاربران VPN با انتخاب نوع اتصال، مسیر خروجی، IPv4 و IPv6، و سطح الزام IPsec؛ بدون اختلال در سرویس‌های موجود.

| کلاس | ورودی VPN | IPv4 | IPv6 | خروجی مطلوب |
|---|---|---|---|---|
| `l2tp-direct` | xl2tpd/PPP معمولی | مستقیم Polaris | مستقیم Polaris | WAN عمومی Polaris |
| `l2tp-gre` | L2TP/PPP فقط برای کاربران انتخابی | GRE به Warden | GRE به Warden | WAN عمومی Warden |
| `ikev2-direct` | IKEv2/IPsec برای iPhone و کاربران مجاز | مستقیم Polaris | مستقیم Polaris | WAN عمومی Polaris |
| `l2tp-ipsec-optional` | L2TP/IPsec در صورت نیاز واقعی و امکان جداسازی امن | با سیاست صریح | با سیاست صریح | مطابق پروفایل؛ نیازمند طراحی جداگانه |

- مسیر انتخابی کاربر باید **برای هر دو خانواده IP یکسان** باشد، مگر انتخاب صریح و مستند دیگری وجود داشته باشد.
- آدرس و Pool کاربران عادی، GRE، iPhone، Docker و WARP نباید تداخل داشته باشد.
- نبود IPv6 عمومی Route‌شده از طرف Provider به‌معنای عدم امکان Dual-Stack نیست: ULA اختصاصی + NAT66 محدود می‌تواند راهکار باشد. WAN `/64` صرفاً on-link است و نباید بدون Route یا Delegation معتبر به کاربران داده شود.
- سیاست مبتنی بر نام PPP بعد از احراز هویت اعمال می‌شود؛ ثبت «IPsec required» در metadata به‌تنهایی الزام رمزنگاری نیست.
- تغییرات MikroTik را توسعه‌دهنده روتر اعمال می‌کند؛ این پروژه فقط مشخصات موردنیاز، آزمون پذیرش و هماهنگی سمت سرور را تهیه می‌کند.

## ۱. راهنمای وضعیت

- **✅ تأییدشده:** خروجی اجرایی/تست واقعی برای دامنه مشخص وجود دارد.
- **🟡 آزمایش موفق، غیردائمی:** کار می‌کند اما lifecycle، reconnect، reboot یا مدیریت عمومی ندارد.
- **🟠 پیاده‌سازی/نصب شده، اعتبارسنجی ناکامل:** کد یا Rule وجود دارد اما ترافیک واقعی یا دوام هنوز ثابت نشده.
- **⬜ انجام‌نشده:** هنوز پیاده‌سازی یا استقرار نشده.
- **🔒 وابسته/مسدود:** اجرای امن نیازمند داده/پیش‌نیاز یا آزمون دیگر است.

## ۲. ماتریس ردیابی همه درخواست‌ها

| ID | درخواست / قابلیت | وضعیت مستند | شواهد و مرز ادعا |
|---|---|---|---|
| R01 | L2TP و PPP برای کاربران موجود | ✅ | اتصال و IPv4 peerهای `.10` و `.11` در زمان‌های مختلف مشاهده شد؛ نام `pppN` تغییر می‌کند |
| R02 | IPv4 مستقیم کاربر معمولی `.10` | ✅ در تست نمونه | مسیر از PPP به `enp1s0` و پیش‌تر پینگ اینترنت IPv4 موفق بود؛ تست Reboot موجود نیست |
| R03 | IPv6 مستقیم کاربر معمولی `.10` | 🟡 | RouterOS با Source ULA انتخابی ۵/۵ پینگ IPv6 و HTTPS `200` گرفت؛ IP عمومی پاسخ Polaris بود |
| R04 | بازیابی رابط PPP بعد از Reconnect برای `.10` | 🟡 | خرابی `ppp1`→`ppp0` رخ داد؛ Rebind دستی Route و قواعد را اصلاح و تست IPv6 را موفق کرد؛ هوک دائمی وجود ندارد |
| R05 | IPv6 از GRE/Warden برای `.11` | ✅ در تست تاریخی | ۵/۵ پاسخ و HTTPS با IPv6 Warden؛ در آخرین خروجی RouterOS، US غیرفعال بود، پس وضعیت زنده فعلی تأیید نشده |
| R06 | IPv4 از GRE/Warden برای `.11` | 🟠 | جدول ۲۰۱/Policy Polaris و Route برگشت/NAT44 Warden نصب؛ شمارنده‌ها در آخرین بررسی مرتبط صفر بودند و آزمون موفق جدید MikroTik ارائه نشده |
| R07 | دائمی‌سازی IPv6 GRE دو سرور | 🟠 | `l2tp6-polaris.timer` و `l2tp6-warden.timer` فعال و آخرین اجرا موفق؛ آزمون کامل Reconnect/Reboot و جلوگیری از قواعد قدیمی باقی است |
| R08 | دائمی‌سازی IPv4 GRE Warden | ⬜ | قواعد آزمایشی اجرا شد؛ Installer اختیاری در مخزن هست ولی استقرار و تست آن گزارش نشده |
| R09 | دائمی‌سازی IPv6 مستقیم روی Polaris | ⬜ | Pilot/Rebind فایل‌های عملیاتی روی میزبان هستند؛ Timer، Hook چندکاربره و آزمون Reboot وجود ندارد |
| R10 | تمام کاربران معمولی L2TP دارای Dual-Stack | ⬜ | فقط نمونه `.10` با IPv6 آزمایش شده؛ تخصیص per-user و اتصال کلاینت‌های دیگر پیاده نشده |
| R11 | IPv6 کاربران LAN پشت روتر | ⬜ | فقط Source IPv6 خود روتر آزمایش شده؛ RA/SLAAC، Prefix مجزای LAN و مسیر برگشت شبکه LAN تأیید نشده |
| R12 | iPhone با IKEv2/IPsec مستقل | ⬜ | در Polaris strongSwan/IKEv2 Listener روی UDP 500/4500 وجود نداشت و SAD=0 |
| R13 | تمام کاربران iPhone دارای IPv4 و IPv6 مستقیم Polaris | ⬜ | Poolهای مستقل دو خانواده، CHILD_SA، گواهی، NAT/Route و تست دستگاه واقعی آماده نیست |
| R14 | ساخت/تبدیل/غیرفعال‌سازی کاربر iPhone از CLI | ⬜ | `tools/ipsec-policy.py` فقط metadata را مدیریت می‌کند؛ credential backend و سرویس IKEv2 وجود ندارد |
| R15 | سیاست IPsec سراسری با انتخاب الزام برای کاربران خاص | 🟠 کد طرح‌واره | مدل global و per-user در Repo و تست‌های unit وجود دارند؛ الزام واقعی XFRM/Endpoint و جلوگیری از Downgrade پیاده نشده |
| R16 | انتخاب مسیر خروجی IPv4+IPv6 برای هر کاربر | 🟠 موردی | Policyهای نمونه در سرورها موجود؛ موتور عمومی multi-user/حفظ هم‌خوانی دو خانواده وجود ندارد |
| R17 | ایمنی WARP، Docker، SSH، Port Forward و NAT | 🟠 نسبی | قواعد آزمایشی محدودند؛ آزمون رگرسیون end-to-end و مالکیت دقیق تمام قواعد هنوز کامل نیست |
| R18 | حذف قواعد بلااستفاده Kasm | ✅ برای بخش iptables | شش Rule runtime و persisted حذف و بکاپ ثبت شد؛ `br_kasm_sidecar` باقی است، بررسی پس از Reboot نشده |
| R19 | فورک، مستندات، نمونه‌ها و تست‌های پایه | ✅ برای کد مخزن | فایل‌های tools/docs/examples/tests و CI موفق سابق ثبت شده؛ کد مخزن مساوی Deploy زنده نیست |
| R20 | ادغام در Main و انتشار نسخه Production | ⬜ | تغییرات در Feature Branch و Draft PR مانده‌اند؛ release gates پاس نشده‌اند |

### شواهد جدید مهم — IPv6 مستقیم `.10`

- آدرس آزمایشی روتر: `fd19:b90e:8c04::11/128` از Prefix ذخیره‌شده `fd19:b90e:8c04::/48`.
- خروجی عمومی Polaris: `2001:19f0:b001:289:5400:6ff:febc:4e96`.
- Ping به `2606:4700:4700::1111`: دو مرحله موفق ۵/۵؛ بعد از پیش‌فرض IPv6 روی اتصال CA نیز ۵/۵ با میانگین حدود ۲۰۳ms.
- تست `api6.ipify.org` با Source انتخابی: پاسخ HTTP 200 و همان IPv6 عمومی Polaris.
- قبل از Rebind، چهارچوب Pilot روی `ppp1` مانده بود درحالی‌که Peer `.10` روی `ppp0` بود؛ قانون Drop پنج بسته را شمرد. بعد از Rebind Route برگشت و ACCEPT روی `ppp0` قرار گرفت؛ تست روتر موفق شد.
- شمارنده‌های NAT66 پیش از تست نهایی صفر نشان داده شدند؛ از آن داده قدیمی نباید نتیجه گرفت که ترافیک موفق بعدی NAT نشده است. اندازه‌گیری هم‌زمان با تست تازه برای تشخیص دقیق ضروری است.
- RouterOS فعلاً Route پیش‌فرض IPv6 از CA و Blackhole ثانویه دارد و Route پیش‌فرض US غیرفعال است؛ این یک انتخاب global در جدول main روتر است و نباید به‌اشتباه به‌عنوان جداسازی per-user تلقی شود.

### شواهد Polaris/Warden و نقاط توجه

- Polaris: WAN مستقیم IPv4/IPv6، Forwarding هر دو خانواده فعال، WARP و GRE هم‌زمان فعال.
- Polaris `systemd-networkd` شبکه `enp1s0` را از Netplan مدیریت می‌کند؛ وجود `accept_ra=0` Kernel همراه با RA Route فعال لزوماً خطا نیست. تغییر کورکورانه sysctl و Restart مدیر شبکه ممنوع.
- IPv6 GRE: جدول ۲۰۲ و Policy اختصاصی `.11`؛ IPv6 مستقیم CA: جدول ۲۰۳ و Policy اختصاصی `.10`؛ IPv4 GRE: جدول ۲۰۱.
- Warden: Route برگشت IPv4/NAT44 برای `.11` آزمایشی اضافه شد؛ IPv6 NAT66 برای `.11` در Reconciler ثبت شده است.
- Ruleهای اختصاصی GRE مربوط به PPP قدیمی ممکن است پس از Reconnect باقی بمانند؛ مدیر دائمی باید آن‌ها را با مالکیت روشن پاک‌سازی کند.
- فایل‌های آزمایشی روی Polaris شامل `polaris-direct6-pilot.sh`، `polaris-direct6-pilot-v2.sh` و `direct6_rebind_polaris.sh` هستند؛ این فایل‌ها برنامه عمومی و دائمی Repo محسوب نمی‌شوند.

## ۳. برنامه اجرایی اولویت‌بندی‌شده

### P0 — تثبیت و Baseline پیش از هر تغییر جدید (اولویت بحرانی)

**وضعیت:** 🟠 در جریان؛ بخشی از Audit انجام شده.

- [x] ثبت حالت فعلی Direct/GRE/IPv4/IPv6 و دو Gateway.
- [x] تأیید موفقیت موردی IPv6 مستقیم `.10` با Ping و HTTPS از روتر.
- [ ] ثبت هم‌زمان Route/Rule/Firewall Counters بعد از تست تازه کاربران `.10` و `.11`.
- [ ] تأیید اینکه اتصال `.11` هنگام آزمون GRE واقعاً Running است؛ خروجی آخر فعلی US را Disabled نشان می‌دهد.
- [ ] تهیه Backup هدفمند از Route/Rule/iptables، Netplan، PPP Hooks، Timerها و سرویس‌هایی که دست‌کاری خواهند شد.
- [ ] شناسایی مالک هر قانون (Pilot، Reconciler، Docker، UFW، WARP، سرویس قدیمی)؛ ممنوعیت Restore جدول کامل یا Flush.
- [ ] وضعیت پروتکل، DNS، IPv6 PMTU و اولویت واقعی Ruleها در هر دو خانواده ثبت شود.

**قبولی:** Baseline قابل تکرار، دسترسی مدیریتی پایدار، بدون Rule مبهم یا Route فاقد مالک در محدوده تغییر.  
**Rollback:** فقط تغییر اختصاصی همین فاز؛ Baseline و سرویس‌های دیگر دست‌نخورده.

### P1 — دائمی‌سازی صحیح IPv6 مستقیم کاربران عادی L2TP

**وضعیت:** 🟡 Pilot موفق، پیاده‌سازی عمومی انجام‌نشده. **اولویت بعدی.**

- [ ] افزودن تخصیص پایدار و بدون برخورد IPv6 `/128` به هر حساب L2TP معمولی از Prefix مستقیم ثبت‌شده؛ بدون تغییر Prefix کلاینت GRE.
- [ ] تشخیص Interface فعلی از Peer IPv4 + هویت احراز‌شده کاربر، با رد حالت چند Interface/حساب تکراری.
- [ ] ساخت Reconciler idempotent برای `ip-up`، `ipv6-up`، `ip-down`، `ipv6-down` و دوره‌ای/Boot؛ حذف قواعد stale بعد از Reconnect یا تغییر `pppN`.
- [ ] نگهداری Route برگشت درست به Interface فعلی و Forward/NAT66 محدود روی WAN Polaris؛ کلاینت GRE هرگز مشمول SNAT Polaris نشود.
- [ ] عدم وابستگی دائمی جدول Direct به Link-local Gateway قدیمی؛ هماهنگی با Route فعلی Networkd/RA و Fail-closed هنگام فقدان WAN.
- [ ] بازبینی تقدم WARP و GRE، جدول‌های اختصاصی، سیاست‌ها و Exception مقصدهای محلی؛ تست نبود نشت بین مسیرها.
- [ ] افزودن عملیات audit/apply/dry-run/remove/rollback و مالکیت آشکار Rules؛ عدم کپی whole iptables snapshot برای بازگردانی.
- [ ] Reconnect آزمایشی با `ppp1→ppp0/ppp2`، چند اتصال هم‌زمان، قطع WAN، Reboot کنترل‌شده و Validation خروجی IPv6 عمومی.
- [ ] ثبت Pool و قابلیت IPv6 در مدیریت حساب L2TP و مستندات CLI.

**قبولی:** حداقل دو حساب L2TP معمولی به‌صورت مستقل IPv4+IPv6 مستقیم دارند؛ Reconnect نام PPP را تغییر بدهد و بدون اجرای دستی Script دوباره کار کند؛ بعد از Reboot پایدار؛ GRE و Docker بی‌تغییر.  
**Rollback:** توقف Reconciler اختصاصی، حذف Policy/NAT/Route فقط با Owner ID و حفظ Fail-closed تا پایان پاک‌سازی؛ احراز عدم حذف NAT66 GRE.

### P2 — تکمیل IPv4 و IPv6 کلاینت‌های انتخابی GRE/Warden

**وضعیت:** 🟠 IPv6 قبلاً عملی موفق؛ IPv4 NAT/Route نصب اما تأیید نهایی ناقص.

- [ ] با فعال بودن `.11` دوباره مسیر IPv4 از MikroTik به اینترنت و Public IP Warden را تست کن.
- [ ] روی Warden هم‌زمان با تست، NAT44، FORWARD و Conntrack شمارش شوند؛ در Polaris جدول ۲۰۱ و Rule Source وارسی شوند.
- [ ] چنانچه WARP واقعاً ترافیک را منحرف می‌کند فقط قانون Source اختصاصی را با بالاترین اولویت لازم اصلاح کن؛ تقدم عددی به‌تنهایی اثبات نقص نیست.
- [ ] پس از موفقیت واقعی IPv4، Installer اختیاری `tools/install-ipv4-egress-persistence.sh` روی Warden با تنظیمات Root-owned و نسخه پشتیبان محدود تست/نصب شود.
- [ ] اعتبارسنجی Reconnect/Timerهای IPv6 موجود، حذف Rule وابسته به PPP قدیمی و ثبات Source Routing هر دو خانواده.
- [ ] آزمایش موازی `.10` Direct و `.11` GRE؛ انتخاب و قطع هر مسیر نباید دیگری را تغییر دهد.

**قبولی:** برای `.11` خروجی IPv4 و IPv6 هر دو مربوط به Warden، برای `.10` هر دو مربوط به Polaris؛ عدم fallback ناخواسته و عبور تست‌های قطع/وصل و Reboot.  
**Rollback:** حذف فقط Route/NAT/Rule مالک سناریوی GRE IPv4/IPv6؛ عدم تغییر سرویس عمومی PPP یا IP Forwarding.

### P3 — Dual-Stack تمام کاربران عادی و LAN اختیاری

**وضعیت:** ⬜.

- [ ] قابلیت Onboarding/Update/Disable همراه با IPv4+IPv6 پرکاربر؛ Poolها، جلوگیری از Collision، بازپس‌گیری امن IP، ثبت تخصیص، اعتبارسنجی ورودی.
- [ ] تفاوت IPv6 خود Router با IPv6 کل LAN را مستند و در صورت نیاز کاربر، برای هر LAN یک `/64` مجزا Route کن؛ RA در سمت LAN روتر به‌عهده توسعه‌دهنده RouterOS.
- [ ] در صورت ارائه Prefix عمومی Route‌شده از ISP، مسیر بدون NAT66 را جدا از fallback ULA+NAT66 پیاده کن.
- [ ] آزمون DNS A/AAAA، HTTP/HTTPS دو خانواده، IPv6 PMTU، Default Routes، IPv4 NAT، IPv6 NAT، قطع و وصل.

**قبولی:** کاربران معمولی جدید از طریق CLI بدون دست‌کاری دستی PPP/iptables دارای Dual-Stack مستقیم می‌شوند؛ Router-only و LAN-wide دو قابلیت متمایز و تست‌شده‌اند.

### P4 — IKEv2/IPsec مستقل برای iPhone با IPv4+IPv6 مستقیم Polaris

**وضعیت:** ⬜؛ فقط طراحی و مستندات Repo.

- [ ] شناسایی نسخه و وضعیت پکیج strongSwan/charon و تداخل Port/Daemon/Firewall؛ Endpoint IKEv2 مستقل روی UDP 500/4500، بدون تغییر Listener فعلی L2TP.
- [ ] تعیین هویت IKE، Domain واقعی، گواهی X.509 معتبر با SAN درست، زنجیره اعتماد و دوران تمدید/ابطال.
- [ ] انتخاب Pool مستقل بدون همپوشانی IPv4 و IPv6 Virtual IP؛ `local_ts` شامل `0.0.0.0/0` و `::/0` و بررسی پذیرش عملی iOS.
- [ ] پیاده‌سازی Auth هر کاربر (EAP-MSCHAPv2 یا EAP-TLS) و مدیریت محرمانه credentialها؛ بدون اشتراک رمز PPP در Repo.
- [ ] تنظیم Routing مستقیم WAN Polaris، NAT44 برای VIP خصوصی و NAT66 محدود برای ULA IPv6 یا Route عمومی واقعی؛ لحاظ XFRM/IPsec و پرهیز از NAT اشتباه برگشت Tunnel.
- [ ] تست واقعی iPhone روی Wi‑Fi و Cellular: احراز هویت، دو VIP، CHILD_SA، IPv4/IPv6 HTTPS، DNS، Reconnect، تعلیق/ابطال حساب.
- [ ] مستندسازی Profile iOS و مدیریت گروهی کاربران، بدون فاش‌کردن Secret.

**قبولی:** کاربر iPhone با حساب اختصاصی به IKEv2 وصل می‌شود و هر دو IP عمومی **Polaris** را می‌بیند؛ اختلالی در L2TP/PPP/GRE فعلی ایجاد نمی‌شود؛ قبل از آن هیچ حسابی «iPhone آماده» خوانده نشود.

### P5 — Global IPsec Policy و انتخاب امنیت هر حساب

**وضعیت:** 🟠 Schema/Validator موجود، Enforcement انجام‌نشده.

- [x] مدل Host-local سراسری برای `plaintext` و `ipsec-required`، مستندات و تست قواعد ساختاری Repo.
- [ ] اتصال Policy به Provisioning واقعی StrongSwan و چرخه credential حساب.
- [ ] هر کاربر «IPsec required» نباید امکان لاگین با همان Identity روی L2TP Plaintext داشته باشد؛ آزمون منفی بای‌پس اجباری.
- [ ] اگر کاربران غیر-iPhone به L2TP/IPsec نیاز داشته باشند، Endpoint/LNS جداگانه و enforce واقعی XFRM/Firewall طراحی و تست شود؛ Flag PPP روی Listener مشترک کافی نیست.
- [ ] امکان ایجاد، تبدیل، غیرفعال‌سازی، لغو دسترسی و گزارش وضعیت **واقعاً enforce‌شده**، نه صرف metadata.
- [ ] مدیریت Certificate/PSK و Secret Rotation، Least Privilege و Audit Log بی‌افشای اطلاعات.

**قبولی:** انتخاب Security per user همزمان در Auth و Firewall/IPsec اجرا شود؛ تست موفق اتصال امن و شکست اتصال غیرامن برای هویت محافظت‌شده ثبت شود.

### P6 — مدیریت تغییرات، CI، رگرسیون، Reboot و انتشار

**وضعیت:** 🟠 مستندات و Unit CI وجود دارد؛ تست یکپارچه/انتشار ناقص.

- [x] فورک، Branch و Draft PR فعال؛ docs/examples/tools/tests و Workflow تست اولیه.
- [ ] جداسازی کد توسعه از Working Tree زنده‌ای که سرویس‌های سرور از آن استفاده می‌کنند؛ عدم Deploy با `git pull` یا `l2tp-manager.sh` خودکار.
- [ ] Audit & Tests برای تخصیص Address، Owner Rules، Firewall، Dynamic PPP، WARP/RA، Fail-closed، Reboot و Rollback.
- [ ] Test Matrix شامل سه کلاس `l2tp-direct`، `l2tp-gre` و `ikev2-direct` با IPv4 و IPv6، تأیید Public Egress و رگرسیون هم‌زمان.
- [ ] بررسی SSH، Docker، UFW، Port Forward، سیستم RA، خدمات فعلی و محدودیت‌های MTU 1280.
- [ ] Release Review، PR، Rollback مستند، ادغام در Main پس از قبولی معیارها، نسخه‌بندی و برنامه آپگرید.

**قبولی:** CI به‌علاوه تست واقعی اتصال‌ها و Reboot، Rollback انجام‌شده و قابل تکرار؛ هیچ Credential داخل Repo نباشد.

### P7 — پاک‌سازی باقی‌مانده Kasm و بدهی‌های قدیمی

**وضعیت:** 🟠 بخشی تکمیل‌شده.

- [x] شش قانون اختصاصی Kasm از iptables Runtime و persisted حذف و Backup تهیه شد.
- [ ] اثبات اینکه `br_kasm_sidecar` دیگر Owner/Dependency ندارد و حذف ایمن آن در صورت لزوم.
- [ ] بررسی Persistence بعد از Reboot و اینکه سرویس‌های دیگر Snapshot قدیمی را بازنمی‌گردانند.
- [ ] حذف خطاهای قدیمی lifecycle و رفتارهای پرخطر `pkill -9` یا Restart سراسری و بازگردانی whole-table در Repository، با تست و Migration امن.

## ۴. ترتیب اجرا و وابستگی‌ها

**اجرای توصیه‌شده:** `P0 → P1 → P2 → P3 → P4 → P5 → P6`؛ `P7` مستقل و بعد از تثبیت مسیرهای VPN.

- ابتدا Pilot Direct را به یک Reconciler واقعی تبدیل کن: تکرار خرابی `ppp1→ppp0` برای تمام کاربران قابل قبول نیست.
- سپس IPv4 GRE را با آزمون واقعی ببند؛ قواعد نصب‌شده بدون Counter و HTTPS Public IP کافی نیستند.
- قابلیت User Lifecycle و Dual-Stack عمومی قبل از افزایش تعداد کاربران لازم است.
- IKEv2 iPhone می‌تواند پس از آماده‌شدن معماری Pool و Direct NAT در یک مسیر توسعه جدا پیاده شود؛ سرویس فعلی `xl2tpd` نباید Restart/Replace شود.
- Flag «IPsec Required» تا زمان وجود Enforcement و آزمون Downgrade در UI/CLI نباید به‌عنوان فعال نمایش داده شود.
- Reboot تأییدشده و Rollback واقعی شرط انتشار است، نه یک کار اختیاری آخر پروژه.

## ۵. نتایج مثبت/منفی که باید در نسخه نهایی ثبت شوند

| پروفایل | IPv4 Internet | IPv6 Internet | Public Exit درست | Reconnect | Reboot | Revoke/Isolation |
|---|---|---|---|---|---|---|
| L2TP معمولی، نمونه `.10` | ✅ قبلی | ✅ جدید | ✅ IPv6 Polaris | 🟠 فقط با Rebind دستی | ⬜ | ⬜ |
| L2TP انتخابی GRE، نمونه `.11` | 🟠 | ✅ تاریخی | ✅ IPv6 Warden تاریخی | 🟠 | ⬜ | 🟠 |
| iPhone IKEv2 مستقیم | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ |
| تمام کاربران عادی تازه | ⬜ خودکار | ⬜ خودکار | ⬜ | ⬜ | ⬜ | ⬜ |

## ۶. ریسک‌ها، ممنوعیت‌ها و Rollback

- **ریسک با اولویت بالا:** PPP Interface نام ثابت ندارد. Ruleهایی که به `ppp1` وابسته باشند، پس از Reconnect ممکن است به Peer دیگری تعلق بگیرند یا بسته‌های مشتری واقعی را Drop کنند.
- **ریسک با اولویت بالا:** Route WAN IPv6 از RA/Networkd می‌آید. جدول اختصاصی با Gateway لینک‌لوکال ثابت باید همگام با وضعیت WAN باشد؛ `accept_ra=0` در Kernel به‌تنهایی نشانه خرابی نیست.
- **ریسک با اولویت بالا:** WARP policy، جدول‌های مجزا و Netfilter در حضور Docker/UFW باید به صورت Effective بررسی شوند؛ Priority قبل از WARP به‌تنهایی اثبات دخالت WARP نیست، خصوصاً وقتی جدول آن Default Route ندارد.
- **ریسک کلیدی IPsec:** PPP Username دیرتر از IPsec شناخته می‌شود؛ Metadata بدون جداسازی واقعی Endpoint/credentials قابل دورزدن است.
- **ریسک MikroTik:** Route پیش‌فرض IPv6 در جدول Main می‌تواند بر تمام ترافیک روتر/LAN اثر بگذارد؛ انتخاب per-user/per-source را توسعه‌دهنده RouterOS باید جدا طراحی و بیازماید.
- **ممنوع:** Flush کلی iptables/nft، Restore کامل Rules، Restart تصادفی `xl2tpd`، Docker، WARP یا Networkd، تغییر IP pool کاربران موجود بدون Migration و اجرای `git pull` به‌عنوان نصب تولید.
- **Rollback موردنیاز هر Milestone:** Backup پیش از تغییر، Owner ID قواعد، Dry-run، دستور حذف فقط منابع همان feature، عدم حذف مسیرهای SSH، معیار توقف و چک رفتار عملی بعد از بازگشت.

## ۷. مرز شواهد و ثبت پیشرفت

این سند با هر تست جدید **تاریخ و شاهد** دریافت می‌کند. تنها وقتی وضعیت به «✅ Production Verified» تبدیل می‌شود که تست end-to-end، reconnect، reboot، failure/rollback و نبود رگرسیون پاس شده باشند.

مخزن GitHub به ماشین‌های Polaris/Warden و RouterOS دسترسی اجرایی ندارد. Commit/CI فقط وضعیت Source را اثبات می‌کند و نصب زنده نیست. آخرین Auditها و تست‌ها از خروجی اپراتور نقل شده‌اند. ابزارها و مستندات پیشین همچنان در `PLAN.md` و فایل‌های docs در دسترس‌اند.
