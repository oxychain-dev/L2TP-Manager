# ISSUE-BACKLOG.md — فهرست کامل Issueهای آماده ثبت

> **وضعیت GitHub:** ایجاد Issue در تاریخ 2026-11-14 با پاسخ HTTP 410 (`Issues has been disabled in this repository`) رد شد. موارد زیر **Issue واقعی GitHub نیستند** و عمداً با شناسهٔ پیگیری محلی `TASK-xxx` مشخص شده‌اند؛ پس از فعال‌سازی GitHub Issues هر بخش را به‌صورت Issue مستقل منتقل و لینک آن را جایگزین کنید.
> این مجموعه از مرور گفتگو، شواهد iPhone IKE/ESP، `PLAN.md`، `GUIDE.md` و کد فعلی development تهیه شده است. موارد تکمیل‌شدهٔ Source CI/ادغام PR به‌عنوان Issue باز تکرار نشده‌اند.

## قواعد پیگیری و اولویت‌ها

- `P0`: شرط لازم پیش از تأیید Stable یا رفع ریسک قطع کاربران؛ `P1`: سازگاری/تکمیل و پذیرش تولید؛ `P2`: محصول آینده (CLI/Portal/Subscription).
- هر وظیفه دارای Scope، Evidence، Definition of Done و پروندهٔ مرجع است. تست واقعی نیازمند **خروجی Polaris/MikroTik** است؛ نبود شواهد = `NOT TESTED`.
- تیک Source implementation به معنی deploy، backend availability، وجود Session واقعی، یا تصدیق IP عمومی نیست.
- برای ایجاد Issue در آینده: GitHub → Repository Settings → General → Features → Issues (توسط مالک/ادمین). پس از فعال‌شدن، متن هر بخش به‌عنوان Issue جداگانه با اولویت در Title منتقل شود.

## خلاصه: 29 Issue پیش‌نویس باز

| شناسهٔ محلی | اولویت | عنوان |
| --- | --- | --- |
| TASK-001 | P0 | iPhone: تطبیق IKE/ESP، Username PPP و خروجی واقعی اینترنت |
| TASK-002 | P0 | پایداری Boot و بازیابی کامل پس از reboot با Rollback |
| TASK-003 | P0 | همسان‌سازی Secret واقعی strongSwan و فایل Global PSK |
| TASK-004 | P0 | مالکیت ایمن Forwardها و حذف pkill/iptables-restore سراسری |
| TASK-005 | P0 | معماری مشترک CRUD حساب PPP و جلوگیری از Restart گسترده |
| TASK-006 | P0 | تأیید تخصیص IP پویا/ثابت و رقابت هم‌زمان در VPS واقعی |
| TASK-007 | P0 | تست واقعی دو تونل Plain L2TP CA1 و CA2 با IP خروجی مشترک |
| TASK-008 | P0 | ممیزی فایروال، NAT44، IPv4 PBR، دسترسی مدیریت و Provider Firewall |
| TASK-009 | P0 | Hook هویت PPP و Session Monitor روی Polaris |
| TASK-010 | P1 | Underlay متفاوت WAN1/WAN2/WAN3 در RouterOS و حفظ route /32 موجود |
| TASK-011 | P1 | Fail-closed Kill Switch و توزیع اتصال بر تونل‌های سالم (PCC/sticky routing) |
| TASK-012 | P1 | IPv4 GRE egress به مقصد متفاوت: NAT/return path واقعی و پایدار |
| TASK-013 | P1 | Direct L2TP IPv6: reconciliation و آدرس‌دهی پس از تعویض pppN |
| TASK-014 | P1 | IPv6 GRE gateway: public prefix/ULA+NAT66/return route و LAN client |
| TASK-015 | P1 | Dual-stack برای کاربران غیر-GRE و مسیرهای متفاوت IPv4/IPv6 |
| TASK-016 | P1 | عیب‌یابی proposalهای قدیمی/اتصال‌های ناموفق بدون ضعیف‌کردن رمزنگاری |
| TASK-017 | P1 | IPsec-required برای حساب خاص: جداسازی endpoint و تست negative plaintext bypass |
| TASK-018 | P1 | Android جدید: استقرار Backend IKEv2 EAP و Profile عملی |
| TASK-019 | P1 | تست سازگاری iOS/Android/Modem/Router و خروجی دستگاه‌محور |
| TASK-020 | P1 | مدیریت Route و Port Forward legacy: جلوگیری از Route flap و exposing management |
| TASK-021 | P1 | تست فشار، MTU/MSS، packet loss، latency، reconnect و محدودیت CPU/RAM |
| TASK-022 | P1 | CI و Release gates قابل تکرار برای ۱۶ تست واقعی، نصب تازه و rollback |
| TASK-023 | P1 | اسنپ‌شات، Backup خصوصی، مانیتورینگ سرویس و ایمیل root |
| TASK-024 | P2 | CLI ساخت نام کلاینت و پروفایل برای iphone|android|modem|router|all |
| TASK-025 | P2 | HTTPS Dashboard امن: ورود Username/Password و اطلاعات حساب خود کاربر |
| TASK-026 | P2 | لینک دعوت ثبت‌نام یک‌بارمصرف با ساخت حساب تراکنشی |
| TASK-027 | P2 | Subscription URL قابل‌ابطال مجزا از Invitation و دانلود امن Profile |
| TASK-028 | P2 | مقیاس‌پذیری و امنیت عملیاتی Portal/Provisioning در VPS کوچک |
| TASK-029 | P1 | بازنگری وضعیت تاریخی PLAN.md و یکپارچگی مستندات مطابق شواهد تازه |

---

## TASK-001 — [P0] iPhone: تطبیق IKE/ESP، Username PPP و خروجی واقعی اینترنت

**وضعیت:** OPEN / NOT TESTED (یا تأیید عملیاتی ناقص)  ·  **مالک:** تعیین‌نشده  ·  **GitHub Issue URL:** هنوز ایجاد نشده است

**Evidence / مسئله**

شواهد: در 14 Nov 2026، IKEv1 ESTABLISHED، CHILD_SA INSTALLED، SAD=2 و ppp2/peer 172.16.101.13 ثبت شد؛ PPP Username و HTTP(S) اgress روی گوشی هنوز مستند نشده است.

**Scope / مراحل**

PPP auth event/PEERNAME را با peer و SA زمانی یکسان تطبیق بده؛ روی خود گوشی IPv4 HTTPS public IP/DNS و در صورت پشتیبانی IPv6 را آزمایش کن؛ reconnect و قطع/وصل NAT را بسنج.

**Definition of Done / معیار پذیرش**

شواهد IKE+CHILD+PPP identity، IP عمومی منطبق و آزمون بازاتصال با کمترین اختلال. نتیجهٔ IPv6 نامعلوم را PASS نزن.

**مرجع داخل مخزن**

`docs/PHASE-1-CLIENT-STABILITY.md` / [GUIDE.md](GUIDE.md)

**شرط ایمنی مشترک:** نه اطلاعات ورود/PSK/کلید XFRM در Issue منتشر شود و نه Start/Stop/Reboot/Firewall/RouterOS بدون Backup، Scope و آزمون Recovery انجام شود.

---

## TASK-002 — [P0] پایداری Boot و بازیابی کامل پس از reboot با Rollback

**وضعیت:** OPEN / NOT TESTED (یا تأیید عملیاتی ناقص)  ·  **مالک:** تعیین‌نشده  ·  **GitHub Issue URL:** هنوز ایجاد نشده است

**Evidence / مسئله**

strongSwan/xl2tpd/timers در لاگ قبل فعال بودند؛ reboot **بعد از** اتصال موفق iPhone و بازیابی GRE/WARP/Forward هنوز آزمایش نشده است.

**Scope / مراحل**

Baseline unit/ExecStart/enablement؛ Snapshot و OOB console؛ maintenance reboot؛ post-boot اصالت VPN، PPP/ESP، GRE، Direct6، Docker، WARP، Forward، Rule/Route و SSH؛ rollback-tested.

**Definition of Done / معیار پذیرش**

همهٔ سرویس‌های لازم و کلاینت‌های واقعی پس از boot سالم و مستقل؛ بدون تغییر پیش‌فرض شبکه، فرمان‌های بازگشت مستند.

**مرجع داخل مخزن**

`docs/STABLE-DEPLOYMENT-GATES.md` / [GUIDE.md](GUIDE.md)

**شرط ایمنی مشترک:** نه اطلاعات ورود/PSK/کلید XFRM در Issue منتشر شود و نه Start/Stop/Reboot/Firewall/RouterOS بدون Backup، Scope و آزمون Recovery انجام شود.

---

## TASK-003 — [P0] همسان‌سازی Secret واقعی strongSwan و فایل Global PSK

**وضعیت:** OPEN / NOT TESTED (یا تأیید عملیاتی ناقص)  ·  **مالک:** تعیین‌نشده  ·  **GitHub Issue URL:** هنوز ایجاد نشده است

**Evidence / مسئله**

Audit قبلی PSK سراسری ۱۸ کاراکتری و active snippet متفاوت را نشان داد؛ سپس iPhone وصل شد؛ وضعیت فعلی فایل‌های disk تأیید نشده است.

**Scope / مراحل**

global-status read-only/credential provenance؛ فقط در نبود IKE SA و پنجرهٔ نگهداری rotate/sync با بک‌آپ؛ تست دقیق restore/clear credentials و reconnect؛ عدم چاپ/hash PSK.

**Definition of Done / معیار پذیرش**

MATCH on-disk؛ IKE/PPP بعد از reboot و rotation آزمایشی؛ عدم افشای کلید و اختلال در دیگر کاربران.

**مرجع داخل مخزن**

`docs/PHASE1-PSK-USERS.md` / [GUIDE.md](GUIDE.md)

**شرط ایمنی مشترک:** نه اطلاعات ورود/PSK/کلید XFRM در Issue منتشر شود و نه Start/Stop/Reboot/Firewall/RouterOS بدون Backup، Scope و آزمون Recovery انجام شود.

---

## TASK-004 — [P0] مالکیت ایمن Forwardها و حذف pkill/iptables-restore سراسری

**وضعیت:** OPEN / NOT TESTED (یا تأیید عملیاتی ناقص)  ·  **مالک:** تعیین‌نشده  ·  **GitHub Issue URL:** هنوز ایجاد نشده است

**Evidence / مسئله**

lib/services.sh از pkill عمومی socat و restore سراسری Firewall و حذف Route قبل از add استفاده می‌کند؛ ممکن است مسیر دیگر کاربران/SSH را قطع کند.

**Scope / مراحل**

فرآیندهای socat اختصاصی پروژه را با pidfile/systemd مدیریت کن؛ Chain/Rule ID scoped؛ atomic forward add/remove/replace؛ جلوگیری از route flap؛ خطا/rollback.

**Definition of Done / معیار پذیرش**

Restart یک Forward سایر سرویس‌ها و Docker/WARP/GRE را قطع نکند؛ CI و آزمایش زنده با چند Forward.

**مرجع داخل مخزن**

`lib/services.sh` / [GUIDE.md](GUIDE.md)

**شرط ایمنی مشترک:** نه اطلاعات ورود/PSK/کلید XFRM در Issue منتشر شود و نه Start/Stop/Reboot/Firewall/RouterOS بدون Backup، Scope و آزمون Recovery انجام شود.

---

## TASK-005 — [P0] معماری مشترک CRUD حساب PPP و جلوگیری از Restart گسترده

**وضعیت:** OPEN / NOT TESTED (یا تأیید عملیاتی ناقص)  ·  **مالک:** تعیین‌نشده  ·  **GitHub Issue URL:** هنوز ایجاد نشده است

**Evidence / مسئله**

مسیر قدیمی منوی ۵ user deletion هنوز xl2tpd و forwards را restart می‌کند؛ مسیر edit متفاوت و session credential cache نامعلوم است.

**Scope / مراحل**

یک writer قفل‌شده برای add/edit/delete/disable/enable؛ عملیات روی disconnected account یا هدفمند؛ preserve comments and legacy; immediate disable semantics یا امتناع؛ backup atomic و rollback.

**Definition of Done / معیار پذیرش**

CA1 هنگام حذف/تعطیل CA2 باقی بماند؛ آدرس‌ها بدون تعارض؛ فقط نشست هدف قطع شود؛ رمزها چاپ نشوند.

**مرجع داخل مخزن**

`lib/users.sh` / [GUIDE.md](GUIDE.md)

**شرط ایمنی مشترک:** نه اطلاعات ورود/PSK/کلید XFRM در Issue منتشر شود و نه Start/Stop/Reboot/Firewall/RouterOS بدون Backup، Scope و آزمون Recovery انجام شود.

---

## TASK-006 — [P0] تأیید تخصیص IP پویا/ثابت و رقابت هم‌زمان در VPS واقعی

**وضعیت:** OPEN / NOT TESTED (یا تأیید عملیاتی ناقص)  ·  **مالک:** تعیین‌نشده  ·  **GitHub Issue URL:** هنوز ایجاد نشده است

**Evidence / مسئله**

Source allocator lock و تست‌های mocked دارد، اما با CHAP واقعی، writers خارجی و live PPP آزمون نشده؛ مخزن به reserved/direct6/GRE references متکی است.

**Scope / مراحل**

تطبیق effective subnet/pool/local IP؛ wildcard و unmanaged CHAP entries؛ دروازه IP release/reuse؛ آدرس‌های reserved/route/forward؛ race 2 admins؛ fresh install؛ atomic rollback؛ کپی خصوصی.

**Definition of Done / معیار پذیرش**

دادهٔ واقعی CA1 دست‌نخورده؛ ۲ درخواست هم‌زمان IP یکتا؛ stale/unknown address fail closed؛ تست no-restart pppd.

**مرجع داخل مخزن**

`tools/plain-l2tp-multiwan.py` / [GUIDE.md](GUIDE.md)

**شرط ایمنی مشترک:** نه اطلاعات ورود/PSK/کلید XFRM در Issue منتشر شود و نه Start/Stop/Reboot/Firewall/RouterOS بدون Backup، Scope و آزمون Recovery انجام شود.

---

## TASK-007 — [P0] تست واقعی دو تونل Plain L2TP CA1 و CA2 با IP خروجی مشترک

**وضعیت:** OPEN / NOT TESTED (یا تأیید عملیاتی ناقص)  ·  **مالک:** تعیین‌نشده  ·  **GitHub Issue URL:** هنوز ایجاد نشده است

**Evidence / مسئله**

RouterOS 7.25.1 و VPS واقعی از طرف ChatGPT وصل نیستند؛ تست موازی سورس به معنای اتصال واقعی نیست. CA1 موجود باید حفظ شود.

**Scope / مراحل**

CA2 با CHAP مستقل و IP جدا از WAN2؛ تأیید WAN underlay؛ CA1 online during create/disconnect/reconnect؛ ترافیک HTTPS از هر دو و مقایسه با Public IPv4 واقعی VPS؛ بدون IPsec/MPPE.

**Definition of Done / معیار پذیرش**

دو Interface PPP و هویت متفاوت هم‌زمان؛ egress مشترک، CA1 بدون drop، NAT/return path بدون loop؛ 16-case acceptance documented.

**مرجع داخل مخزن**

`docs/PLAIN-L2TP-MULTIWAN.md` / [GUIDE.md](GUIDE.md)

**شرط ایمنی مشترک:** نه اطلاعات ورود/PSK/کلید XFRM در Issue منتشر شود و نه Start/Stop/Reboot/Firewall/RouterOS بدون Backup، Scope و آزمون Recovery انجام شود.

---

## TASK-008 — [P0] ممیزی فایروال، NAT44، IPv4 PBR، دسترسی مدیریت و Provider Firewall

**وضعیت:** OPEN / NOT TESTED (یا تأیید عملیاتی ناقص)  ·  **مالک:** تعیین‌نشده  ·  **GitHub Issue URL:** هنوز ایجاد نشده است

**Evidence / مسئله**

UDP 1701 و 500/4500 listener فعال مشاهده شده‌اند؛ وجود listener به معنی عبور provider یا حفظ SSH نیست؛ forwarding و NAT موثر نیازمند شواهد‌اند.

**Scope / مراحل**

iptables/nftables effective و upstream VPS filter؛ scoped UDP 1701/500/4500؛ no public Winbox/API exposure؛ source policy per-PPP and matching conntrack؛ MSS/MTU و return route.

**Definition of Done / معیار پذیرش**

دسترسی مدیریت فقط مجاز؛ دو PPP به egress مطلوب می‌رسند؛ عدم تداخل با Direct6/GRE/WARP/Docker؛ rules idempotent.

**مرجع داخل مخزن**

`lib/install.sh` / [GUIDE.md](GUIDE.md)

**شرط ایمنی مشترک:** نه اطلاعات ورود/PSK/کلید XFRM در Issue منتشر شود و نه Start/Stop/Reboot/Firewall/RouterOS بدون Backup، Scope و آزمون Recovery انجام شود.

---

## TASK-009 — [P0] Hook هویت PPP و Session Monitor روی Polaris

**وضعیت:** OPEN / NOT TESTED (یا تأیید عملیاتی ناقص)  ·  **مالک:** تعیین‌نشده  ·  **GitHub Issue URL:** هنوز ایجاد نشده است

**Evidence / مسئله**

pppd ip-up/down hook به‌صورت اختیاری در سورس آماده است؛ روی VPS نصب و رفتار rapid pppN reuse تأیید نشده است.

**Scope / مراحل**

--check/--install با مجوز owner/dir؛ compare PEERNAME/IPREMOTE/ifindex با journal؛ uptime/bytes و stale records؛ reconnect/boot/parallel؛ no secret logging.

**Definition of Done / معیار پذیرش**

verified vs inferred کاملاً جدا؛ هیچ stale record به Username جدید منتسب نشود؛ هویت چند PPP قابل‌بازبینی.

**مرجع داخل مخزن**

`tools/ppp-session-hook.py` / [GUIDE.md](GUIDE.md)

**شرط ایمنی مشترک:** نه اطلاعات ورود/PSK/کلید XFRM در Issue منتشر شود و نه Start/Stop/Reboot/Firewall/RouterOS بدون Backup، Scope و آزمون Recovery انجام شود.

---

## TASK-010 — [P1] Underlay متفاوت WAN1/WAN2/WAN3 در RouterOS و حفظ route /32 موجود

**وضعیت:** OPEN / NOT TESTED (یا تأیید عملیاتی ناقص)  ·  **مالک:** تعیین‌نشده  ·  **GitHub Issue URL:** هنوز ایجاد نشده است

**Evidence / مسئله**

هر دو L2TP به یک مقصد لزوماً روی WAN جدا نمی‌روند؛ route CA1 به WAN1 ممکن است CA2 را منحرف کند.

**Scope / مراحل**

Audit واقعی VRF/routing table/routing rule/NAT و Gateway؛ صحت RouterOS 7.25.1 connect-to=@VRF؛ staged CA2; ca3 future؛ هیچ تغییر MikroTik خودکار انجام نشود.

**Definition of Done / معیار پذیرش**

یک CA1 روی WAN1 و CA2 روی WAN2 با trace قابل‌مشاهده؛ no route leak/fallback؛ CA1 immutable.

**مرجع داخل مخزن**

`docs/PLAIN-L2TP-MULTIWAN.md` / [GUIDE.md](GUIDE.md)

**شرط ایمنی مشترک:** نه اطلاعات ورود/PSK/کلید XFRM در Issue منتشر شود و نه Start/Stop/Reboot/Firewall/RouterOS بدون Backup، Scope و آزمون Recovery انجام شود.

---

## TASK-011 — [P1] Fail-closed Kill Switch و توزیع اتصال بر تونل‌های سالم (PCC/sticky routing)

**وضعیت:** OPEN / NOT TESTED (یا تأیید عملیاتی ناقص)  ·  **مالک:** تعیین‌نشده  ·  **GitHub Issue URL:** هنوز ایجاد نشده است

**Evidence / مسئله**

نیاز آیندهٔ کاربر؛ source VPN سرور قرار نیست packet steering RouterOS را انجام دهد.

**Scope / مراحل**

طرح RouterOS-mark/PCC برای NEW connection؛ حفظ 5-tuple affinity/conntrack؛ health-check و failover deterministic؛ drop if all CA tunnels down؛ capacity awareness optional.

**Definition of Done / معیار پذیرش**

Established flows مسیر/egress عوض نکنند؛ new flows فقط healthy؛ اگر همه down شدند، traffic مستقیم WAN leak نکند؛ یک TCP flow aggregation ادعا نشود.

**مرجع داخل مخزن**

`docs/PLAIN-L2TP-MULTIWAN.md` / [GUIDE.md](GUIDE.md)

**شرط ایمنی مشترک:** نه اطلاعات ورود/PSK/کلید XFRM در Issue منتشر شود و نه Start/Stop/Reboot/Firewall/RouterOS بدون Backup، Scope و آزمون Recovery انجام شود.

---

## TASK-012 — [P1] IPv4 GRE egress به مقصد متفاوت: NAT/return path واقعی و پایدار

**وضعیت:** OPEN / NOT TESTED (یا تأیید عملیاتی ناقص)  ·  **مالک:** تعیین‌نشده  ·  **GitHub Issue URL:** هنوز ایجاد نشده است

**Evidence / مسئله**

وضعیت قبلی ingress source route/remote NAT به معنی خروجی واقعاً تأییدشده نیست.

**Scope / مراحل**

تست واقعی client IPv4 HTTPS روی سمت remote GRE gateway با packet counters, return route/NAT44, ssh/no impact و persistence reconnect.

**Definition of Done / معیار پذیرش**

Public egress و return symmetry تأیید، بدون تغییر مسیر کاربران غیرمنتخب.

**مرجع داخل مخزن**

`docs/ipv4-gre-egress.md` / [GUIDE.md](GUIDE.md)

**شرط ایمنی مشترک:** نه اطلاعات ورود/PSK/کلید XFRM در Issue منتشر شود و نه Start/Stop/Reboot/Firewall/RouterOS بدون Backup، Scope و آزمون Recovery انجام شود.

---

## TASK-013 — [P1] Direct L2TP IPv6: reconciliation و آدرس‌دهی پس از تعویض pppN

**وضعیت:** OPEN / NOT TESTED (یا تأیید عملیاتی ناقص)  ·  **مالک:** تعیین‌نشده  ·  **GitHub Issue URL:** هنوز ایجاد نشده است

**Evidence / مسئله**

Pilot IPv6 HTTPS/5 پینگ قبلاً روی یک client موفق ولی بعد از interface renumbering نیازمند اصلاح دستی شده بود؛ source reconciler توسعه یافته اما deployment جدید و recovery نه.

**Scope / مراحل**

انتقال scoped از pilot به direct6-reconcile hooks/timer؛ تست static user identity مستقل از pppN؛ ULA routing, LAN/128 if applicable, PBR، RA uplink/accept_ra و reboot.

**Definition of Done / معیار پذیرش**

مشتری منتخب IPv6 HTTPS واقعی را بعد از reconnect/boot حفظ کند؛ دیگر کاربران و WARP/GRE مختل نشوند.

**مرجع داخل مخزن**

`docs/direct-dualstack.md` / [GUIDE.md](GUIDE.md)

**شرط ایمنی مشترک:** نه اطلاعات ورود/PSK/کلید XFRM در Issue منتشر شود و نه Start/Stop/Reboot/Firewall/RouterOS بدون Backup، Scope و آزمون Recovery انجام شود.

---

## TASK-014 — [P1] IPv6 GRE gateway: public prefix/ULA+NAT66/return route و LAN client

**وضعیت:** OPEN / NOT TESTED (یا تأیید عملیاتی ناقص)  ·  **مالک:** تعیین‌نشده  ·  **GitHub Issue URL:** هنوز ایجاد نشده است

**Evidence / مسئله**

برنامهٔ قبلی prefix/64 LAN، gateway/128، NAT66 و RA؛ end-to-end روی همه مشتریان اجرا نشده است.

**Scope / مراحل**

از ISP prefix قابل route یا ULA scoped/NAT66 تصمیم‌گیری؛ GRE MTU/RA/forwarding، برگشت Gateway و RouterOS IPv6 default; source IPv6 test LAN/router.

**Definition of Done / معیار پذیرش**

IPv6 HTTPS و DNS AAAA واقعی با مسیر رفت‌وبرگشت صحیح، stable after reconnect/reboot، بدون IPv4 regression.

**مرجع داخل مخزن**

`docs/ipv6-gre.md` / [GUIDE.md](GUIDE.md)

**شرط ایمنی مشترک:** نه اطلاعات ورود/PSK/کلید XFRM در Issue منتشر شود و نه Start/Stop/Reboot/Firewall/RouterOS بدون Backup، Scope و آزمون Recovery انجام شود.

---

## TASK-015 — [P1] Dual-stack برای کاربران غیر-GRE و مسیرهای متفاوت IPv4/IPv6

**وضعیت:** OPEN / NOT TESTED (یا تأیید عملیاتی ناقص)  ·  **مالک:** تعیین‌نشده  ·  **GitHub Issue URL:** هنوز ایجاد نشده است

**Evidence / مسئله**

نیاز صریح همهٔ کاربران IPv4/IPv6 و تمایز ingress/egress؛ وجود IPv6CP link-local کافی نیست.

**Scope / مراحل**

برای هر حساب نوع route انتخابی، IPv4+IPv6 peer/LAN addressing و DNS، policy isolation، NAT/return path، conflict detection و profile compatibility.

**Definition of Done / معیار پذیرش**

IPv4 و IPv6 هرکدام تست بیرونی واقعی، بدون source leak و regression.

**مرجع داخل مخزن**

`docs/direct-dualstack.md` / [GUIDE.md](GUIDE.md)

**شرط ایمنی مشترک:** نه اطلاعات ورود/PSK/کلید XFRM در Issue منتشر شود و نه Start/Stop/Reboot/Firewall/RouterOS بدون Backup، Scope و آزمون Recovery انجام شود.

---

## TASK-016 — [P1] عیب‌یابی proposalهای قدیمی/اتصال‌های ناموفق بدون ضعیف‌کردن رمزنگاری

**وضعیت:** OPEN / NOT TESTED (یا تأیید عملیاتی ناقص)  ·  **مالک:** تعیین‌نشده  ·  **GitHub Issue URL:** هنوز ایجاد نشده است

**Evidence / مسئله**

قبل از iPhone success لاگ IKEv2 NO_PROPOSAL_CHOSEN و IKEv1 3DES/DES/MODP768/1024 رد شده، و Pluginهای اختیاری missing بودند.

**Scope / مراحل**

هر failed request را با client-type و proposals classify؛ بدون Enable کردن DES/3DES صرفاً برای compatibility؛ کاهش نویز اختیاری swanctl اگر بدون اثر functional؛ test doc.

**Definition of Done / معیار پذیرش**

IKEv1 AES256/SHA256/MODP2048 همچنان برای iPhone موفق؛ weak suites absent؛ clean actionable diagnostics.

**مرجع داخل مخزن**

`docs/PHASE-1-CLIENT-STABILITY.md` / [GUIDE.md](GUIDE.md)

**شرط ایمنی مشترک:** نه اطلاعات ورود/PSK/کلید XFRM در Issue منتشر شود و نه Start/Stop/Reboot/Firewall/RouterOS بدون Backup، Scope و آزمون Recovery انجام شود.

---

## TASK-017 — [P1] IPsec-required برای حساب خاص: جداسازی endpoint و تست negative plaintext bypass

**وضعیت:** OPEN / NOT TESTED (یا تأیید عملیاتی ناقص)  ·  **مالک:** تعیین‌نشده  ·  **GitHub Issue URL:** هنوز ایجاد نشده است

**Evidence / مسئله**

کاربر نهایتاً PSK offered را مدنظر داشت؛ در سورس انتخاب PSK فقط metadata است و دسترسی plaintext را مسدود نمی‌کند.

**Scope / مراحل**

در صورت نیاز مستقل، endpoint/auth جدا برای IPsec-only؛ هیچ claim security بدون enforce firewall/XFRM/PPP admission؛ test downgrade and wrong credential.

**Definition of Done / معیار پذیرش**

کاربر protected-only بدون ESP موفق به auth/forwarding نشود؛ کاربران plain همچنان با سیاست مورد انتظار فعال.

**مرجع داخل مخزن**

`docs/ipsec-selective.md` / [GUIDE.md](GUIDE.md)

**شرط ایمنی مشترک:** نه اطلاعات ورود/PSK/کلید XFRM در Issue منتشر شود و نه Start/Stop/Reboot/Firewall/RouterOS بدون Backup، Scope و آزمون Recovery انجام شود.

---

## TASK-018 — [P1] Android جدید: استقرار Backend IKEv2 EAP و Profile عملی

**وضعیت:** OPEN / NOT TESTED (یا تأیید عملیاتی ناقص)  ·  **مالک:** تعیین‌نشده  ·  **GitHub Issue URL:** هنوز ایجاد نشده است

**Evidence / مسئله**

در سورس generator پروفایل strongSwan Android و candidate IKEv2 EAP وجود دارد، اما سرویس EAP/VIP/dual-stack برای کاربران واقعی deploy و تست نشده است.

**Scope / مراحل**

IKEv2 separate from IKEv1/PSK, per-user EAP secrets, certificates/CA verification, IPv4+IPv6 VIP, NAT routing, Android import/reconnect, coexistence with xl2tpd.

**Definition of Done / معیار پذیرش**

Android modern profile واقعی authenticate شود، egress واقعی و lifecycle safe، هیچ cross-protocol credential confusion.

**مرجع داخل مخزن**

`docs/mobile-profiles.md` / [GUIDE.md](GUIDE.md)

**شرط ایمنی مشترک:** نه اطلاعات ورود/PSK/کلید XFRM در Issue منتشر شود و نه Start/Stop/Reboot/Firewall/RouterOS بدون Backup، Scope و آزمون Recovery انجام شود.

---

## TASK-019 — [P1] تست سازگاری iOS/Android/Modem/Router و خروجی دستگاه‌محور

**وضعیت:** OPEN / NOT TESTED (یا تأیید عملیاتی ناقص)  ·  **مالک:** تعیین‌نشده  ·  **GitHub Issue URL:** هنوز ایجاد نشده است

**Evidence / مسئله**

iPhone manual L2TP/PSK کار کرده؛ همهٔ دستگاه‌ها از پروتکل یکسان یا mobileconfig/sswan پشتیبانی نمی‌کنند.

**Scope / مراحل**

ماتریس firmware/app، manual import و signed/unsigned Apple profile در صورت نیاز، Android IKEv2, مودم/روتر vendor-specific؛ test actual import و handshake.

**Definition of Done / معیار پذیرش**

برای هر platform artifact validated و failure documented؛ گزینه all شامل چند خروجیِ متفاوت باشد نه یک فایل عمومی.

**مرجع داخل مخزن**

`docs/mobile-profiles.md` / [GUIDE.md](GUIDE.md)

**شرط ایمنی مشترک:** نه اطلاعات ورود/PSK/کلید XFRM در Issue منتشر شود و نه Start/Stop/Reboot/Firewall/RouterOS بدون Backup، Scope و آزمون Recovery انجام شود.

---

## TASK-020 — [P1] مدیریت Route و Port Forward legacy: جلوگیری از Route flap و exposing management

**وضعیت:** OPEN / NOT TESTED (یا تأیید عملیاتی ناقص)  ·  **مالک:** تعیین‌نشده  ·  **GitHub Issue URL:** هنوز ایجاد نشده است

**Evidence / مسئله**

l2tp-routes-manager.sh و Forward menu در برخی مسیرها Route را قبل از add حذف می‌کنند؛ standard MikroTik Winbox/API Forward ممکن است public شود.

**Scope / مراحل**

Ownership route table; replace idempotent; no global delete; validation before reload; safeguards public management exposure; no dynamic pppN permanent bindings.

**Definition of Done / معیار پذیرش**

بدون قطع CA1، DNS، SSH، GRE، WARP؛ رفتارهای rollback tests در staging و live maintenance.

**مرجع داخل مخزن**

`l2tp-routes-manager.sh` / [GUIDE.md](GUIDE.md)

**شرط ایمنی مشترک:** نه اطلاعات ورود/PSK/کلید XFRM در Issue منتشر شود و نه Start/Stop/Reboot/Firewall/RouterOS بدون Backup، Scope و آزمون Recovery انجام شود.

---

## TASK-021 — [P1] تست فشار، MTU/MSS، packet loss، latency، reconnect و محدودیت CPU/RAM

**وضعیت:** OPEN / NOT TESTED (یا تأیید عملیاتی ناقص)  ·  **مالک:** تعیین‌نشده  ·  **GitHub Issue URL:** هنوز ایجاد نشده است

**Evidence / مسئله**

VPS کوچک و RouterOS MIPSBE تک‌هسته‌ای؛ تونل‌های هم‌زمان می‌توانند throughput/NAT/CPU را تحت فشار بگذارند؛ PPP MTU/MRU 1280 سابقه دارد.

**Scope / مراحل**

small bounded load tests; TCP MSS/PMTUD, UDP1701 under NAT, fragmentation, drop, CPU/RAM/flash writes, NAT affinity, reconnect storms.

**Definition of Done / معیار پذیرش**

پروفایل baseline/threshold؛ هیچ تغییر tuning بدون داده؛ no packet loss regression در ظرفیت متعارف.

**مرجع داخل مخزن**

`PLAN.md` / [GUIDE.md](GUIDE.md)

**شرط ایمنی مشترک:** نه اطلاعات ورود/PSK/کلید XFRM در Issue منتشر شود و نه Start/Stop/Reboot/Firewall/RouterOS بدون Backup، Scope و آزمون Recovery انجام شود.

---

## TASK-022 — [P1] CI و Release gates قابل تکرار برای ۱۶ تست واقعی، نصب تازه و rollback

**وضعیت:** OPEN / NOT TESTED (یا تأیید عملیاتی ناقص)  ·  **مالک:** تعیین‌نشده  ·  **GitHub Issue URL:** هنوز ایجاد نشده است

**Evidence / مسئله**

CI با ۴۸ تست آفلاین موفق است؛ ShellCheck اجرای واقعی و ارتباط VPS/MikroTik باید جدا گزارش شود.

**Scope / مراحل**

Matrix unit/integration/fresh install/upgrade, topology fixtures, ShellCheck full, fail injections, CI log redaction, docs & status versioning; report NOT TESTED live.

**Definition of Done / معیار پذیرش**

هر release tag پشت evidence replayable و tests pass؛ تفاوت source vs live صریح؛ rollback verified.

**مرجع داخل مخزن**

`docs/STABLE-DEPLOYMENT-GATES.md` / [GUIDE.md](GUIDE.md)

**شرط ایمنی مشترک:** نه اطلاعات ورود/PSK/کلید XFRM در Issue منتشر شود و نه Start/Stop/Reboot/Firewall/RouterOS بدون Backup، Scope و آزمون Recovery انجام شود.

---

## TASK-023 — [P1] اسنپ‌شات، Backup خصوصی، مانیتورینگ سرویس و ایمیل root

**وضعیت:** OPEN / NOT TESTED (یا تأیید عملیاتی ناقص)  ·  **مالک:** تعیین‌نشده  ·  **GitHub Issue URL:** هنوز ایجاد نشده است

**Evidence / مسئله**

پیام You have new mail /var/mail/root در log بود؛ علت تأیید نشده؛ snapshot/monitoring/recovery بعد از rollout نشده است.

**Scope / مراحل**

read-only mail headers & sender + cron/systemd failure; secret-safe backup/retention/root permissions; bounded health checks, disk/RAM, alerts for VPN, PPP, GRE, NAT, certificate/rekey.

**Definition of Done / معیار پذیرش**

restore drill و alert tests؛ بدون ارسال credential به mail/log، اصل least privilege.

**مرجع داخل مخزن**

`GUIDE.md` / [GUIDE.md](GUIDE.md)

**شرط ایمنی مشترک:** نه اطلاعات ورود/PSK/کلید XFRM در Issue منتشر شود و نه Start/Stop/Reboot/Firewall/RouterOS بدون Backup، Scope و آزمون Recovery انجام شود.

---

## TASK-024 — [P2] CLI ساخت نام کلاینت و پروفایل برای iphone|android|modem|router|all

**وضعیت:** OPEN / NOT TESTED (یا تأیید عملیاتی ناقص)  ·  **مالک:** تعیین‌نشده  ·  **GitHub Issue URL:** هنوز ایجاد نشده است

**Evidence / مسئله**

User workflow آینده: نام client سپس انتخاب device و ایجاد PPP/IKEv2 user + پروفایل؛ قطعات مختلف سورس جدا از هم وجود دارند اما unified wizard و export کامل ندارند.

**Scope / مراحل**

capability detection and protocol selection; transactional IP/username allocation; per-device profile; controlled secret delivery; no static assumptions; safe rerun/rollback.

**Definition of Done / معیار پذیرش**

هر device import validated؛ `all` چند فرمت سازگار ایجاد کند؛ هیچ global PSK را بدون کنترل منتشر نکند.

**مرجع داخل مخزن**

`docs/FUTURE-SELF-SERVICE.md` / [GUIDE.md](GUIDE.md)

**شرط ایمنی مشترک:** نه اطلاعات ورود/PSK/کلید XFRM در Issue منتشر شود و نه Start/Stop/Reboot/Firewall/RouterOS بدون Backup، Scope و آزمون Recovery انجام شود.

---

## TASK-025 — [P2] HTTPS Dashboard امن: ورود Username/Password و اطلاعات حساب خود کاربر

**وضعیت:** OPEN / NOT TESTED (یا تأیید عملیاتی ناقص)  ·  **مالک:** تعیین‌نشده  ·  **GitHub Issue URL:** هنوز ایجاد نشده است

**Evidence / مسئله**

Web UI/HTML self-service روی repo فعلی پیاده‌سازی نشده است؛ کاربر می‌خواهد هر حساب مشخصات و پروفایل خود را ببیند.

**Scope / مراحل**

non-root TLS service; hashed passwords, anti-enumeration, rate limit, CSRF, Secure cookies/2FA optional, user isolation, login/logout, profile download ACL, password rotation.

**Definition of Done / معیار پذیرش**

کاربر فقط دادهٔ خودش را ببیند؛ هیچ روت/فایل secret مستقیم در Web tier؛ تست privilege boundaries.

**مرجع داخل مخزن**

`docs/FUTURE-SELF-SERVICE.md` / [GUIDE.md](GUIDE.md)

**شرط ایمنی مشترک:** نه اطلاعات ورود/PSK/کلید XFRM در Issue منتشر شود و نه Start/Stop/Reboot/Firewall/RouterOS بدون Backup، Scope و آزمون Recovery انجام شود.

---

## TASK-026 — [P2] لینک دعوت ثبت‌نام یک‌بارمصرف با ساخت حساب تراکنشی

**وضعیت:** OPEN / NOT TESTED (یا تأیید عملیاتی ناقص)  ·  **مالک:** تعیین‌نشده  ·  **GitHub Issue URL:** هنوز ایجاد نشده است

**Evidence / مسئله**

درخواست تعداد زیادی مشتری: admin یک URL بدهد، مشتری Username/Password انتخاب و وارد Dashboard شود؛ هنوز پیاده‌سازی نشده است.

**Scope / مراحل**

CSPRNG token hashed at rest, TTL/limit/revocation, atomic one-time consume, anti-duplicate username/PP IP, privileged helper scoped, rollback provisioning, audit and load tests.

**Definition of Done / معیار پذیرش**

Token replay rejected؛ failed create no orphan login؛ new user authenticated redirects dashboard؛ abuse/cross-user proof.

**مرجع داخل مخزن**

`docs/FUTURE-SELF-SERVICE.md` / [GUIDE.md](GUIDE.md)

**شرط ایمنی مشترک:** نه اطلاعات ورود/PSK/کلید XFRM در Issue منتشر شود و نه Start/Stop/Reboot/Firewall/RouterOS بدون Backup، Scope و آزمون Recovery انجام شود.

---

## TASK-027 — [P2] Subscription URL قابل‌ابطال مجزا از Invitation و دانلود امن Profile

**وضعیت:** OPEN / NOT TESTED (یا تأیید عملیاتی ناقص)  ·  **مالک:** تعیین‌نشده  ·  **GitHub Issue URL:** هنوز ایجاد نشده است

**Evidence / مسئله**

دعوت یک‌بارمصرف با URL اشتراکِ بازخوانی‌شونده یکسان نیست؛ endpoint فعلی وجود ندارد.

**Scope / مراحل**

read-only per-user scoped token, expiration/revocation, no-store, TLS, no PSK/PPP password in URL or cache, per-device schema, authentication for sensitive reveal/download, rotation & audit.

**Definition of Done / معیار پذیرش**

stolen/revoked URL cannot read other users یا global PSK؛ invitation consumed independent of subscription.

**مرجع داخل مخزن**

`docs/FUTURE-SELF-SERVICE.md` / [GUIDE.md](GUIDE.md)

**شرط ایمنی مشترک:** نه اطلاعات ورود/PSK/کلید XFRM در Issue منتشر شود و نه Start/Stop/Reboot/Firewall/RouterOS بدون Backup، Scope و آزمون Recovery انجام شود.

---

## TASK-028 — [P2] مقیاس‌پذیری و امنیت عملیاتی Portal/Provisioning در VPS کوچک

**وضعیت:** OPEN / NOT TESTED (یا تأیید عملیاتی ناقص)  ·  **مالک:** تعیین‌نشده  ·  **GitHub Issue URL:** هنوز ایجاد نشده است

**Evidence / مسئله**

برای تعداد بالای کاربران و ثبت‌نام هم‌زمان نیاز به quota/monitoring/DB/serialization/restore داریم؛ طرح آینده است.

**Scope / مراحل**

separate privileged minimal helper and non-root web app, address pool exhaustion behavior, concurrent signups, DB migrations, rate limits, metrics, audit redaction, backup/restore and capacity budget.

**Definition of Done / معیار پذیرش**

بدون race/secret leakage در هم‌زمانی بالا؛ service remains within measured VPS resource constraints.

**مرجع داخل مخزن**

`docs/FUTURE-SELF-SERVICE.md` / [GUIDE.md](GUIDE.md)

**شرط ایمنی مشترک:** نه اطلاعات ورود/PSK/کلید XFRM در Issue منتشر شود و نه Start/Stop/Reboot/Firewall/RouterOS بدون Backup، Scope و آزمون Recovery انجام شود.

---

## TASK-029 — [P1] بازنگری وضعیت تاریخی PLAN.md و یکپارچگی مستندات مطابق شواهد تازه

**وضعیت:** OPEN / NOT TESTED (یا تأیید عملیاتی ناقص)  ·  **مالک:** تعیین‌نشده  ·  **GitHub Issue URL:** هنوز ایجاد نشده است

**Evidence / مسئله**

PLAN.md یک تاریخچهٔ مفصل با بندهای قبلاً NOT VERIFIED دارد؛ پس از iPhone IKE/CHILD موفق، بعضی متن‌های Phase-1 قدیمی ممکن است دیگر دقیق نباشند.

**Scope / مراحل**

به‌روزرسانی وضعیت به تفکیک source implemented / live verified / inferred / not tested؛ حذف تناقض در README/PLAN/AGENTS/PHASE1؛ ثبت traceability به issue drafts و commit.

**Definition of Done / معیار پذیرش**

هیچ claim قدیمی با گزارش جدید تعارض نکند؛ رویداد 2026-11-14 با زمان و scope واضح در changelog.

**مرجع داخل مخزن**

`PLAN.md` / [GUIDE.md](GUIDE.md)

**شرط ایمنی مشترک:** نه اطلاعات ورود/PSK/کلید XFRM در Issue منتشر شود و نه Start/Stop/Reboot/Firewall/RouterOS بدون Backup، Scope و آزمون Recovery انجام شود.

---

## انتشار کنترل‌شده پس از فعال‌شدن GitHub Issues

این فایل حاوی **۲۹ Draft مستقل** است و تا فعال‌شدن Issues هیچ Issue واقعی نمی‌سازد. مالک مخزن باید در Settings → General → Features گزینهٔ Issues را فعال کند.

پس از فعال‌سازی، می‌توان از `tools/publish-issue-backlog.py` استفاده کرد. این ابزار **پیش‌فرض dry-run** دارد و `--apply` نیازمند GitHub CLI (`gh`) احراز هویت‌شده و تعیین صریح مخزن است. نیازی به اجرای آن با root یا روی VPS نیست.

~~~bash
(
  set -eu
  repo=$(git rev-parse --show-toplevel)
  python3 "$repo/tools/publish-issue-backlog.py"
)
~~~

برای ایجاد واقعی فقط **بعد از بازبینی عنوان و متن هر ۲۹ مورد و فعال شدن Issues**:

~~~bash
(
  set -eu
  repo=$(git rev-parse --show-toplevel)
  python3 "$repo/tools/publish-issue-backlog.py" --apply --repo oxychain-dev/L2TP-Manager
)
~~~

ابزار موارد موجود را با شناسهٔ `TASK-xxx` یا عنوان تطبیق می‌دهد و از ایجاد تکراری جلوگیری می‌کند. اگر خطا رخ دهد، متوقف می‌شود؛ پیش از اجرای مجدد وضعیت GitHub باید بررسی شود. هر Issue با Tracking ID خودش ایجاد می‌شود و سپس می‌توان بر اساس وابستگی‌ها اولویت‌بندی کرد.