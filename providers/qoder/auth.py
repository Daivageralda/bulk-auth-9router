"""
Qoder Authentication - Google OAuth Flow
Handles browser automation for device flow (refactored from qoder-autopilot)
"""
import asyncio
from camoufox.async_api import AsyncCamoufox
from browserforge.fingerprints import Screen
from config import HEADLESS, LOGIN_TIMEOUT, SCREENSHOTS_DIR
async def authenticate_device_flow(email, password, auth_url):
    """Authenticate to Qoder via Google OAuth using device flow auth_url
    
    Args:
        email: Google account email
        password: Google account password
        auth_url: Device flow auth URL (direct to device/selectAccounts with params)
        
    Returns:
        bool: True if authentication succeeded (OAuth completed)
    
    """
    print(f"  Starting browser for {email}...")
    
    try:
        # Launch Camoufox with anti-detect fingerprinting
        browser = await AsyncCamoufox(
            headless=HEADLESS,
            screen=Screen(max_width=1920, max_height=1080),
        ).start()
        
        page = await browser.new_page()
        page.set_default_timeout(30000)
        
        # Navigate to device/selectAccounts URL directly
        await page.goto(auth_url, wait_until='domcontentloaded')
        await asyncio.sleep(3)
        
        # Take screenshot for debugging
        screenshot_path = SCREENSHOTS_DIR / f"device_page_{email.split('@')[0]}.png"
        await page.screenshot(path=str(screenshot_path))
        
        # Wait for page to fully load
        await asyncio.sleep(2)
        
        # Click "Sign in with Google" button
        try:
            # Try multiple selectors
            google_btn = page.locator('a[href*="/sso/login/google"]').first
            count = await google_btn.count()
            
            if count > 0:
                await google_btn.click()
                await asyncio.sleep(3)
            else:
                # Fallback: construct direct SSO URL
                sso_url = f"https://qoder.com/sso/login/google?redirect_uri={auth_url}"
                await page.goto(sso_url, wait_until='domcontentloaded')
                await asyncio.sleep(2)
        except Exception as e:
            print(f"  ❌ Error clicking Google button: {e}")
            # Fallback: construct direct SSO URL
            print("  Trying direct SSO URL...")
            sso_url = f"https://qoder.com/sso/login/google?redirect_uri={auth_url}"
            await page.goto(sso_url, wait_until='domcontentloaded')
            await asyncio.sleep(2)
        
        # Google OAuth flow
        success = await handle_google_oauth(page, email, password)
        
        await browser.close()
        
        return success
        
    except Exception as e:
        print(f"  ❌ Auth error: {e}")
        try:
            await browser.close()
        except:
            pass
        return False

async def handle_google_oauth(page, email, password):
    """Handle Google OAuth steps"""
    deadline = asyncio.get_event_loop().time() + LOGIN_TIMEOUT
    
    email_filled = False
    password_filled = False
    google_page_reached = False  # Track if we actually reached Google login
    
    while asyncio.get_event_loop().time() < deadline:
        try:
            url = page.url
            
            # Mark that we reached Google accounts page
            if 'accounts.google.com' in url:
                google_page_reached = True
            
            # Only check for success redirect AFTER we've been to Google
            if google_page_reached:
                # Check if back to Qoder (success) - use strict domain check
                if url.startswith('https://qoder.com/') and '/users/sign-in' not in url and '/sso/login' not in url:
                    print("  ✅ OAuth completed, redirected to Qoder")
                    # Wait 5s for server to process callback and generate device token
                    print("  ⏳ Waiting 5s for server to process device token...")
                    await asyncio.sleep(5)
                    return True
                
                # Check if on device selectAccounts page (success)
                if url.startswith('https://qoder.com/device/selectAccounts'):
                    print("  ✅ Reached device selectAccounts page")
                    # Click Continue button if present
                    try:
                        continue_btn = page.locator('button:has-text("Continue")').first
                        if await continue_btn.count() > 0:
                            await continue_btn.click()
                            await asyncio.sleep(2)
                            print("  ✅ Clicked Continue on device auth")
                    except:
                        pass
                    # Wait 5s for server to process device token
                    print("  ⏳ Waiting 5s for server to process device token...")
                    await asyncio.sleep(5)
                    return True
            
            # On Google accounts page
            if 'accounts.google.com' in url:
                # Email step
                if not email_filled:
                    email_input = page.locator('input[type="email"]').first
                    count = await email_input.count()
                    
                    if count > 0:
                        await email_input.fill(email)
                        await asyncio.sleep(1)
                        
                        # Click Continue/Next button (NOT press Enter)
                        try:
                            next_btn = page.locator('button:has-text("Next"), button[type="button"]:has-text("Continue"), div[role="button"]:has-text("Next")').first
                            btn_count = await next_btn.count()
                            
                            if btn_count > 0:
                                await next_btn.click()
                                email_filled = True
                                await asyncio.sleep(3)
                                continue
                        except Exception as e:
                            pass
                        
                        # Fallback: press Enter
                        await page.keyboard.press('Enter')
                        email_filled = True
                        await asyncio.sleep(3)
                        continue
                    else:
                        # Try alternative selectors
                        alt_input = page.locator('input[name="identifier"], input#identifierId').first
                        if await alt_input.count() > 0:
                            await alt_input.fill(email)
                            await asyncio.sleep(1)
                            await page.keyboard.press('Enter')
                            email_filled = True
                            await asyncio.sleep(3)
                            continue
                
                # Password step
                if email_filled and not password_filled:
                    password_input = page.locator('input[type="password"]').first
                    if await password_input.count() > 0:
                        print(f"  🔐 Filling password...")
                        await password_input.fill(password)
                        await asyncio.sleep(1)
                        
                        # Click Continue/Next button (NOT press Enter)
                        try:
                            next_btn = page.locator('button:has-text("Next"), button[type="button"]:has-text("Continue"), div[role="button"]:has-text("Next")').first
                            if await next_btn.count() > 0:
                                print("  ✅ Password filled, clicking Continue/Next...")
                                await next_btn.click()
                                password_filled = True
                                await asyncio.sleep(4)
                                continue
                        except:
                            pass
                        
                        # Fallback: press Enter
                        print("  ✅ Password filled, pressing Enter (fallback)...")
                        await page.keyboard.press('Enter')
                        password_filled = True
                        await asyncio.sleep(4)
                        continue
                
                # Consent page
                consent_btn = page.locator('button:has-text("Continue")').first
                if await consent_btn.count() > 0:
                    await consent_btn.click()
                    await asyncio.sleep(2)
                    continue
            
            await asyncio.sleep(1)
            
        except Exception as e:
            print(f"  OAuth step error: {e}")
            await asyncio.sleep(1)
    
    print(f"  ❌ Login timeout after {LOGIN_TIMEOUT}s")
    return False
