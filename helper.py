import re
import time
from typing import List, Tuple

from fuzzywuzzy import fuzz
from selenium.common.exceptions import StaleElementReferenceException, WebDriverException
from selenium.webdriver.common.by import By

def normalize_name(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", (text or "")).lower()).strip()

def first_name_only(raw: str) -> str:
    if not raw:
        return ""
    # "Last, First ..." -> take first after comma
    if "," in raw:
        after = raw.split(",", 1)[1].strip()
        return after.split()[0].lower() if after else ""
    # Otherwise first token
    return normalize_name(raw).split()[0] if raw else ""

def last_name_tokens(raw: str):
    """Return tokens we consider 'last names' from the target patient_name."""
    if not raw:
        return []
    if "," in raw:
        last = raw.split(",", 1)[0]
        return [t for t in normalize_name(last).split() if t]
    # No comma -> assume "First Last ..." -> everything but first is last
    toks = normalize_name(raw).split()
    return toks[1:] if len(toks) > 1 else []

def token_similarity(a: str, b: str) -> float:
    return fuzz.token_set_ratio(a, b) / 100.0

def strong_enough_match(target_full: str, candidate_full: str,
                        base_threshold: float = 0.70,
                        relaxed_threshold: float = 0.60,
                        last_partial_thresh: int = 80) -> tuple[bool, float, str]:
    """
    Decide if candidate matches target_full strongly enough.
    Returns (ok, score_used, reason).
    """
    t_norm = normalize_name(target_full)
    c_norm = normalize_name(candidate_full)

    score_token = fuzz.token_set_ratio(t_norm, c_norm) / 100.0
    score_partial = fuzz.partial_ratio(t_norm, c_norm) / 100.0

    first_ok = first_name_only(target_full) == first_name_only(candidate_full)
    last_tokens = last_name_tokens(target_full)
    last_ok = any(fuzz.partial_ratio(ln, c_norm) >= last_partial_thresh for ln in last_tokens)

    # 1) standard rule
    if score_token >= base_threshold:
        return True, score_token, "token_set >= base_threshold"

    # 2) first name exact + relaxed global similarity
    if first_ok and score_token >= relaxed_threshold:
        return True, score_token, "first name exact + relaxed token_set"

    # 3) first name exact + any last name partial good
    if first_ok and last_ok:
        return True, max(score_token, score_partial), "first exact + last partial"

    # 4) partial similarity bailout (high)
    if score_partial >= base_threshold:
        return True, score_partial, "partial >= base_threshold"

    return False, score_token, "no rule matched"



def _visible_non_loading_options(driver) -> List[Tuple[object, str]]:
    out = []
    try:
        options = driver.find_elements(By.CSS_SELECTOR, ".mat-autocomplete-panel mat-option")
        for o in options:
            try:
                if not o.is_displayed():
                    continue
                txt = o.text.strip()
                if not txt:
                    continue
                if txt.lower() in ("loading...", "no data", "no results", "loading"):
                    continue
                out.append((o, txt))
            except StaleElementReferenceException:
                continue
    except Exception:
        pass
    return out


def _click_option_by_text(driver, target_text: str, retries: int = 3, sleep: float = 0.2) -> bool:
    css = ".mat-autocomplete-panel mat-option"
    last_exc = None
    for _ in range(retries):
        try:
            options = driver.find_elements(By.CSS_SELECTOR, css)
            for o in options:
                try:
                    if o.is_displayed() and o.text.strip() == target_text:
                        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", o)
                        try:
                            o.click()
                        except WebDriverException:
                            driver.execute_script("arguments[0].click();", o)
                        return True
                except StaleElementReferenceException as e:
                    last_exc = e
                    continue
        except Exception as e:
            last_exc = e
        time.sleep(sleep)
    if last_exc:
        print(f"[doc_type] Click by text failed: {last_exc}")
    return False