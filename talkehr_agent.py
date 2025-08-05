import re
import time
from typing import Optional

from rapidfuzz import fuzz, process
from selenium.common import StaleElementReferenceException, TimeoutException, WebDriverException
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from helper import _click_option_by_text, _visible_non_loading_options, strong_enough_match


def click_patient_row_with_retries(driver, idx, expected_text, retries=3, sleep=0.2):
    css = ".go-search-dropdown.patient-drop-down mat-list-item.mat-list-item"
    last_exc = None
    for attempt in range(1, retries + 1):
        try:
            rows = driver.find_elements(By.CSS_SELECTOR, css)
            if not rows:
                time.sleep(sleep)
                continue
            if idx < len(rows):
                elem = rows[idx]
            else:
                elem = next((r for r in rows if expected_text.lower() in r.text.lower()), None)
                if not elem:
                    time.sleep(sleep)
                    continue
            driver.execute_script("arguments[0].scrollIntoView({block:'center'});", elem)
            try:
                elem.click()
            except WebDriverException:
                driver.execute_script("arguments[0].click();", elem)
            return True
        except StaleElementReferenceException as e:
            last_exc = e
            time.sleep(sleep)
            continue
        except Exception as e:
            last_exc = e
            time.sleep(sleep)
            continue

    print(f"Failed to click patient after {retries} retries. Last error: {last_exc}")
    return False


def first_name_only(raw: str) -> str:
    if "," in raw:
        parts = raw.split(",", 1)[1].strip().split()
        return parts[0].lower() if parts else ""
    # Else take the first token
    tokens = re.sub(r"[^\w\s]", " ", raw).strip().split()
    return tokens[0].lower() if tokens else ""

def token_similarity(a: str, b: str) -> float:
    return fuzz.token_set_ratio(a, b) / 100.0

class TalkEHRBot:
    def __init__(self, driver):
        self.driver = driver

    def split_name(self, name):
        parts = name.lower().split()
        return (parts[0], parts[-1]) if len(parts) >= 2 else (parts[0], '')

    def name_similarity(self, candidate, target):
        can_first, can_last = self.split_name(candidate)
        tgt_first, tgt_last = self.split_name(target)
        last_sim = fuzz.ratio(can_last, tgt_last) / 100.0
        first_sim = fuzz.ratio(can_first, tgt_first) / 100.0
        return 0.8 * last_sim + 0.2 * first_sim

    def normalize_name(self, name):
        cleaned = re.sub(r'[^\w\s]', '', name).lower()
        words = cleaned.split()
        words.sort()
        return ' '.join(words)

    def click_patient_row_with_retries(driver, idx, expected_text, retries=3, sleep=0.2):
        css = ".go-search-dropdown.patient-drop-down mat-list-item.mat-list-item"
        last_exc = None
        for _ in range(retries):
            try:
                rows = driver.find_elements(By.CSS_SELECTOR, css)
                if not rows:
                    time.sleep(sleep)
                    continue
                elem = rows[idx] if idx < len(rows) else None
                if elem is None:
                    # fallback: find by text
                    elem = next((r for r in rows if expected_text.lower() in r.text.lower()), None)
                    if elem is None:
                        time.sleep(sleep)
                        continue
                driver.execute_script("arguments[0].scrollIntoView({block:'center'});", elem)
                try:
                    elem.click()
                except Exception:
                    driver.execute_script("arguments[0].click();", elem)
                return True
            except StaleElementReferenceException as e:
                last_exc = e
                time.sleep(sleep)
                continue
            except Exception as e:
                last_exc = e
                time.sleep(sleep)
                continue
        print(f"Failed to click patient after {retries} retries. Last error: {last_exc}")
        return False

    # ---- main function ----
    def select_patient(self, date_of_birth, patient_name) -> bool:
        try:
            search_input = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.ID, "docSavePatName"))
            )
        except TimeoutException:
            print("Could not find patient search input.")
            return False
        except Exception as e:
            print(f"Unexpected error locating search input: {e}")
            return False

        try:
            search_input.clear()
            search_query = date_of_birth if date_of_birth else patient_name
            search_input.send_keys(search_query)
            search_input.send_keys(Keys.ENTER)

            time.sleep(5)

            result_list = WebDriverWait(self.driver, 30).until(
                EC.visibility_of_element_located((By.CSS_SELECTOR, ".go-search-dropdown.patient-drop-down"))
            )
        except TimeoutException:
            print("Patient dropdown never appeared.")
            return False
        except Exception as e:
            print(f"Unexpected error while searching patient: {e}")
            return False
        try:
            patients = result_list.find_elements(By.CSS_SELECTOR, "mat-list-item.mat-list-item")
        except StaleElementReferenceException:
            patients = self.driver.find_elements(
                By.CSS_SELECTOR,
                ".go-search-dropdown.patient-drop-down mat-list-item.mat-list-item"
            )

        if not patients:
            print("No patients returned.")
            return False

        target_full = patient_name
        if len(patients) == 1:
            try:
                lines = patients[0].text.split('\n')
                name = lines[0].strip() if lines else ""
                ok, score, why = strong_enough_match(target_full, name)
                print(f"Comparing '{name}' vs '{patient_name}' — {score:.3f} ({why})")
                if ok:
                    return click_patient_row_with_retries(self.driver, 0, name, retries=3)
                else:
                    print(f"Single result found but not strong enough: '{name}' (expected '{patient_name}')")
                    return False
            except Exception as e:
                print(f"Failed handling single patient result: {e}")
                return False

        print(f"{len(patients)} results found. Listing info and similarities:")
        fresh_rows = self.driver.find_elements(
            By.CSS_SELECTOR, ".go-search-dropdown.patient-drop-down mat-list-item.mat-list-item"
        )
        mrn_pattern = re.compile(r"MRN:(\d+)")
        best_idx = None
        best_reason = ""
        best_score = -1.0
        chosen_name = ""
        chosen_mrn = 0

        for i, pat in enumerate(fresh_rows):
            try:
                lines = pat.text.split('\n')
                if not lines:
                    continue
                name = lines[0].strip()
                ok, score, why = strong_enough_match(target_full, name)
                print(f"    Candidate: '{name}' — {score:.3f} ({why})")

                mrn_match = mrn_pattern.search(pat.text)
                mrn = int(mrn_match.group(1)) if mrn_match else 0
                if ok:
                    if score > best_score or (abs(score - best_score) < 1e-9 and mrn < chosen_mrn):
                        best_idx = i
                        best_score = score
                        best_reason = why
                        chosen_name = name
                        chosen_mrn = mrn

            except StaleElementReferenceException:
                print("A patient row went stale; skipping.")
                continue
            except Exception as e:
                print(f"Error parsing patient row: {e}")
                continue

        if best_idx is not None:
            print(f"Selecting '{chosen_name}' (MRN: {chosen_mrn}) with score {best_score:.3f} ({best_reason})")
            ok = click_patient_row_with_retries(self.driver, best_idx, chosen_name, retries=3)
            if ok:
                return True
            print("Retry click failed.")
            return False

        print("No close name match found.")
        print("Available names:", [fr.text.split("\n")[0].strip() for fr in fresh_rows if fr.text])
        return False

    def select_doc_type(
            self,
            doc_type: str,
            threshold: int = 80,
            poll: float = 0.2,
            max_wait: Optional[float] = None,
            accept_first_if_no_match: bool = False
    ) -> bool:
        start = time.time()
        try:
            doc_type_input = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.ID, "txtdocType"))
            )
            doc_type_input.clear()
            for ch in doc_type:
                doc_type_input.send_keys(ch)
                time.sleep(0.05)
            time.sleep(3)
        except Exception as e:
            print(f"[doc_type] Could not type into input: {e}")
            return False
        while True:
            if max_wait is not None and (time.time() - start) > max_wait:
                print(f"[doc_type] Gave up after {max_wait}s waiting for dropdown/options.")
                return False
            opts = _visible_non_loading_options(self.driver)
            if opts:
                break
            time.sleep(poll)
        target_norm = self.normalize_name(doc_type)
        best_text, best_score = None, 0
        for _, text_raw in opts:
            text_norm = self.normalize_name(text_raw)
            if target_norm in text_norm or text_norm in target_norm:
                if _click_option_by_text(self.driver, text_raw):
                    print(f"Selected doc type (substring/equality): {text_raw}")
                    return True
            score = fuzz.token_set_ratio(target_norm, text_norm)
            print(f"   – '{text_raw}' -> {score}")
            if score > best_score:
                best_score, best_text = score, text_raw
        if best_text and best_score >= threshold:
            if _click_option_by_text(self.driver, best_text):
                print(f"Selected doc type (fuzzy {best_score}): {best_text}")
                return True
            else:
                print("[doc_type] Best option went stale or could not be clicked even after retries.")
                return False
        if accept_first_if_no_match and opts:
            first_text = opts[0][1]
            if _click_option_by_text(self.driver, first_text):
                print(f"Selected first visible doc type (no fuzzy match): {first_text}")
                return True

        print(f"No matching doc type found for '{doc_type}'.")
        return False

    def select_doc_sub_type(self, doc_sub_type):
        sub_type_input = WebDriverWait(self.driver, 10).until(
            EC.element_to_be_clickable((By.ID, "txtdocSubType"))
        )
        sub_type_input.clear()
        for char in doc_sub_type[:5]:
            sub_type_input.send_keys(char)
            time.sleep(0.1)
        try:
            dropdown_options = WebDriverWait(self.driver, 10).until(
                EC.visibility_of_all_elements_located((By.CSS_SELECTOR, "mat-option"))
            )
        except Exception as e:
            print(f"Subtype dropdown didn't appear: {e}")
            return False

        option_texts = [option.text.strip() for option in dropdown_options if option.text.strip()]
        if not option_texts:
            print("No options found in the dropdown.")
            return False
        match = process.extractOne(
            doc_sub_type, option_texts, scorer=fuzz.token_sort_ratio
        )
        if match:
            best_text, score, idx = match
            print(f"Selected top match: '{best_text}' (score: {score})")
            for option in dropdown_options:
                if option.text.strip() == best_text:
                    option.click()
                    return True
            return None
        else:
            print(f"No options available to match for '{doc_sub_type}'.")
            return False

    def select_assigned_to(self, assigned_to: str, fallback: str = "Asim Ali",
                           threshold: int = 80) -> bool:
        def _type_and_pick(target: str) -> bool:
            label_xpath = "//mat-label[contains(text(),'Assigned To')]/ancestor::label"
            try:
                label_el = WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.XPATH, label_xpath))
                )
                input_id = label_el.get_attribute("for")
                assigned_input = WebDriverWait(self.driver, 10).until(
                    EC.element_to_be_clickable((By.ID, input_id))
                )
            except Exception as e:
                print(f"Unable to locate 'Assigned To' input: {e}")
                return False
            try:
                assigned_input.clear()

                for ch in target[:3]:
                    assigned_input.send_keys(ch)
                    time.sleep(0.08)
                time.sleep(3)
                try:
                    options = WebDriverWait(self.driver, 7).until(
                        EC.visibility_of_all_elements_located(
                            (By.CSS_SELECTOR, ".cdk-overlay-pane mat-option")
                        )
                    )
                except TimeoutException:
                    print(f"'Assigned To' dropdown didn't appear for '{target}'.")
                    return False
                target_norm = self.normalize_name(target)
                best_score = 0
                best_option = None
                for option in options:
                    try:
                        text = option.text.strip()
                    except StaleElementReferenceException:
                        continue
                    text_norm = self.normalize_name(text)
                    score = fuzz.token_set_ratio(target_norm, text_norm)
                    print(f"Comparing '{target}' <-> '{text}': {score}")
                    if score > best_score:
                        best_score = score
                        best_option = option
                if best_option and best_score >= threshold:
                    selected_text = best_option.text.strip()
                    try:
                        best_option.click()
                    except StaleElementReferenceException:
                        try:
                            all_opts = self.driver.find_elements(By.CSS_SELECTOR, ".cdk-overlay-pane mat-option")
                            for o in all_opts:
                                if o.text.strip() == selected_text:
                                    o.click()
                                    break
                        except Exception as e:
                            print(f"Retry click failed: {e}")
                            return False
                    print(f"Selected 'Assigned To' (fuzzy): {selected_text} (score {best_score})")
                    return True
                print(f"No fuzzy match for '{target}'. Options were: {[o.text for o in options]}")
                return False
            except Exception as e:
                print(f"Unexpected error in _type_and_pick('{target}'): {e}")
                return False
        if _type_and_pick(assigned_to):
            return True
        print(f"Falling back to '{fallback}' …")
        return _type_and_pick(fallback)

    def switch_to_talker_tab(self):
        for handle in self.driver.window_handles:
            self.driver.switch_to.window(handle)
            time.sleep(1)
            if "talkehr" in self.driver.title.lower() or "talkehr" in self.driver.current_url.lower():
                print("Switched to talkEHR tab!")
                return True
        print("talkEHR tab not found.")
        return False

    def add_comments(self, comments):
        try:
            comments_input = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.ID, "txtComments"))
            )
            comments_input.clear()
            comments_input.send_keys(comments)
            print("Entered comments.")
            return True
        except Exception as e:
            print(f"Failed to enter comments: {e}")
            return False

    def get_url(self):
        if not self.switch_to_talker_tab():
            print("talkEHR tab not found, cannot proceed.")
            return None

        try:
            iframe = self.driver.find_element(By.ID, "docIframeView")
            link = iframe.get_attribute("src")
            if link:
                print("IFRAME LINK:", link)
                return link
            else:
                print("No link found in iframe, checking table for unread rows...")
        except Exception as e:
            print(f"Iframe not found immediately: {e}. Checking table for unread rows...")

        try:
            table = self.driver.find_element(By.CSS_SELECTOR, 'table.mat-table')
            rows = table.find_elements(By.CSS_SELECTOR, "tr.mat-row.cdk-row.tr-unread.ng-star-inserted")
            if not rows:
                print("No unread rows found.")
                return None
            else:
                first_row = rows[0]
                view_link = first_row.find_element(By.XPATH, ".//a[contains(text(), 'View')]")
                view_link.click()
                print("Clicked 'View'. Waiting for modal and iframe...")
                wait = WebDriverWait(self.driver, 15)
                iframe = wait.until(
                    EC.presence_of_element_located((By.ID, "docIframeView"))
                )
                link = iframe.get_attribute("src")
                print("IFRAME LINK:", link)
                return link
        except Exception as e:
            print(f"Error during table fallback: {e}")
            return None

    def save_button(self):
        save_button = WebDriverWait(self.driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, "//button[.//span[text()='Save']]"))
        )
        save_button.click()
        print("Save button clicked.")


    def cancel_button(self):
        btn = WebDriverWait(self.driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, "//button[.//span[normalize-space()='Cancel']]"))
        )
        btn.click()
        print("Save button clicked.")

