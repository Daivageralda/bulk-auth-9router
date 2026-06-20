"""
Google OAuth form filling logic
"""
import asyncio

from utils.logger import print_info


async def fill_google_email(page, email):
    """Fill email field on Google login"""
    for selector in ["#identifierId"]:
        try:
            await page.wait_for_selector(selector, state="visible", timeout=3000)
        except Exception:
            pass

        locator = page.locator(selector).first
        if await locator.count() == 0 or not await locator.is_visible():
            continue

        await locator.scroll_into_view_if_needed()
        await locator.click(force=True)
        await asyncio.sleep(0.2)

        try:
            await locator.press("Control+a")
            await locator.press("Backspace")
        except Exception:
            pass

        try:
            await locator.press_sequentially(email, delay=60)
        except Exception:
            continue

        await asyncio.sleep(0.5)
        value = await locator.input_value()
        if email.lower() != str(value).lower().strip():
            continue

        clicked = await _click_google_next(page)
        if not clicked:
            await locator.press("Enter")
        await asyncio.sleep(1.0)
        return True

    return False


async def fill_google_password(page, password):
    """Fill password field on Google login"""
    for selector in ['input[name="Passwd"]', 'input[type="password"]']:
        try:
            await page.wait_for_selector(selector, state="visible", timeout=3000)
        except Exception:
            pass

        locator = page.locator(selector).first
        if await locator.count() == 0 or not await locator.is_visible():
            continue

        await locator.scroll_into_view_if_needed()
        await locator.click(force=True)
        await asyncio.sleep(0.2)

        try:
            await locator.press("Control+a")
            await locator.press("Backspace")
        except Exception:
            pass

        try:
            await locator.press_sequentially(password, delay=70)
        except Exception:
            continue

        await asyncio.sleep(0.5)
        value = await locator.input_value()
        if len(str(value)) < len(password):
            continue

        clicked = await _click_google_next(page)
        if not clicked:
            await locator.press("Enter")
        await asyncio.sleep(1.0)
        return True

    return False


async def click_continue_button(page):
    """Click generic continue/next/accept buttons"""
    await page.evaluate("""() => {
        for (const sel of [
            '#gaplustosNext button', '#identifierNext button',
            '#passwordNext button', '#submit', '#confirm'
        ]) {
            const el = document.querySelector(sel);
            if (el && el.offsetParent !== null) { el.click(); return; }
        }
        const keywords = [
            'next','continue','accept','understand','agree','ok','got it',
            'login','sign in','mengerti','lanjutkan','setuju','masuk',
            'lewati','berikutnya',
        ];
        for (const btn of document.querySelectorAll(
            'button, div[role="button"], input[type="submit"]'
        )) {
            if (!btn.offsetParent) continue;
            const txt = (btn.textContent || btn.value || '').toLowerCase().trim();
            if (!txt) continue;
            if (keywords.some(k => txt.includes(k))) { btn.click(); return; }
        }
    }""")


async def _handle_google_consent(page):
    """Handle Google consent/allow screen + welcome page"""
    try:
        current_url = page.url
    except Exception:
        return False
    if "accounts.google.com" not in current_url:
        return False

    try:
        return bool(await page.evaluate("""() => {
            // Check for welcome page first
            const welcomeHeading = document.querySelector('h1, h2');
            if (welcomeHeading && welcomeHeading.textContent.toLowerCase().includes('welcome')) {
                // Scroll down to reveal Accept/Continue button
                window.scrollTo(0, document.body.scrollHeight);
                // Wait a bit then look for button
                setTimeout(() => {}, 500);
            }
            
            const el = document.querySelector(
                '#submit_approve_access button, #submit_approve_access'
            );
            if (el && el.offsetParent !== null) { el.click(); return true; }
            const keywords = [
                'continue','allow','accept','agree','lanjut','разрешить','продовжити',
                'дозволити','weiter','erlauben','continuer','autoriser','accepter',
                'continuar','permitir','aceptar','続行','허용','继续','允许','同意',
            ];
            for (const btn of document.querySelectorAll(
                'button, div[role="button"]'
            )) {
                const txt = (btn.textContent || '').trim().toLowerCase();
                if (!txt || btn.offsetParent === null) continue;
                if (keywords.some(k => txt.includes(k))) {
                    btn.click(); return true;
                }
            }
            return false;
        }"""))
    except Exception:
        return False


async def _click_google_next(page):
    try:
        return bool(await page.evaluate("""() => {
            const bySubmit = document.querySelector(
                '#identifierNext button, #passwordNext button'
            );
            if (bySubmit && bySubmit.offsetParent !== null) {
                bySubmit.click(); return true;
            }
            for (const el of document.querySelectorAll(
                'div.VfPpkd-RLmnJb, button, div[role="button"]'
            )) {
                const parentBtn = el.closest('button, div[role="button"]') || el;
                if (parentBtn && parentBtn.offsetParent !== null) {
                    parentBtn.click(); return true;
                }
            }
            return false;
        }"""))
    except Exception:
        return False
