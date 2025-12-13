"""Kabutan.jp data retrieval module"""
import requests
from bs4 import BeautifulSoup
from typing import Optional, Dict
import time
import re


class KabutanAPI:
    """Kabutan.jp data retrieval class"""

    BASE_URL = "https://kabutan.jp/stock/"
    FINANCE_URL = "https://kabutan.jp/stock/finance"
    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }

    @staticmethod
    def _get_page_content(code: str, page_type: str = 'stock') -> Optional[BeautifulSoup]:
        """
        Get page content from Kabutan

        Args:
            code: Stock code (4-digit, e.g., "7203")
            page_type: Page type ('stock' or 'finance')

        Returns:
            BeautifulSoup object or None if failed
        """
        try:
            # Remove .T suffix if present
            code = code.replace('.T', '')

            if page_type == 'finance':
                url = f"{KabutanAPI.FINANCE_URL}?code={code}"
            else:
                url = f"{KabutanAPI.BASE_URL}?code={code}"

            response = requests.get(url, headers=KabutanAPI.HEADERS, timeout=10)
            response.raise_for_status()

            # Add delay to avoid rate limiting
            time.sleep(0.5)

            return BeautifulSoup(response.content, 'lxml')
        except Exception as e:
            print(f"Error: Failed to retrieve Kabutan page ({code}): {e}")
            return None

    @staticmethod
    def _extract_number(text: str) -> Optional[float]:
        """
        Extract numeric value from text

        Args:
            text: Text containing number (e.g., "1,234.56円", "123.45")

        Returns:
            Numeric value or None if extraction failed or text is "－"
        """
        if not text:
            return None

        # Check if text is "－" or contains only "－"
        if text.strip() == '－' or text.strip() == '-':
            return None

        try:
            # Remove commas, yen symbol, whitespace
            cleaned = re.sub(r'[,円\s]', '', text)
            # Extract number (including negative)
            match = re.search(r'-?\d+\.?\d*', cleaned)
            if match:
                return float(match.group())
        except Exception:
            pass

        return None

    @staticmethod
    def get_eps(code: str, verbose: bool = False) -> Optional[float]:
        """
        Get revised EPS (修正1株益) from Kabutan

        Args:
            code: Stock code (4-digit, e.g., "7203")
            verbose: Display detailed logs

        Returns:
            EPS value or None if unable to retrieve
        """
        if verbose:
            print(f"Retrieving EPS from Kabutan: {code}")

        # Get finance page
        soup = KabutanAPI._get_page_content(code, page_type='finance')
        if not soup:
            if verbose:
                print(f"  ✗ Failed to retrieve finance page")
            return None

        try:
            # Look for tables with "修正1株益" header
            tables = soup.find_all('table')
            for table in tables:
                # Find header row
                headers = table.find_all('th', scope='col')
                header_texts = [h.get_text(strip=True).replace('\n', '').replace(' ', '')
                               for h in headers]

                # Check if this table has "修正1株益" column
                eps_col_index = None
                for i, text in enumerate(header_texts):
                    if '修正1株益' in text:
                        eps_col_index = i
                        break

                if eps_col_index is not None:
                    # Adjust index: first column is th (決算期), so td indices are shifted by -1
                    td_index = eps_col_index - 1

                    tbody = table.find('tbody')
                    if tbody:
                        data_rows = tbody.find_all('tr')

                        # Step 1: Try to find company forecast (予) first
                        for row in reversed(data_rows):
                            if row.find('th', scope='row') is None:
                                continue

                            row_th = row.find('th', scope='row')
                            if not row_th or 'oc_btn' in str(row.get('class', [])):
                                continue

                            period = row_th.get_text(strip=True)

                            # Only look for forecast data (marked with "予")
                            if '予' not in period:
                                continue

                            # Skip comparison rows
                            if '前期比' in period or '前年同期比' in period or '同期比' in period:
                                continue

                            cells = row.find_all('td')
                            if len(cells) > td_index >= 0:
                                eps_text = cells[td_index].get_text(strip=True)
                                # Check if forecast data is available
                                if eps_text == '－':
                                    if verbose:
                                        print(f"  ⊘ Skipping {period}: Forecast EPS is '－'")
                                    continue
                                eps_value = KabutanAPI._extract_number(eps_text)
                                if eps_value is not None:
                                    if verbose:
                                        print(f"  ✓ Successfully retrieved EPS: {eps_value} ({period} - Forecast)")
                                    return eps_value

                        # Step 2: Fallback to actual results if forecast not found
                        if verbose:
                            print(f"  → Forecast not available, falling back to actual results")

                        for row in reversed(data_rows):
                            if row.find('th', scope='row') is None:
                                continue

                            row_th = row.find('th', scope='row')
                            if not row_th or 'oc_btn' in str(row.get('class', [])):
                                continue

                            period = row_th.get_text(strip=True)

                            # Skip forecast data
                            if '予' in period:
                                continue

                            # Skip comparison rows
                            if '前期比' in period or '前年同期比' in period or '同期比' in period:
                                if verbose:
                                    print(f"  ⊘ Skipping {period}: Comparison data")
                                continue

                            cells = row.find_all('td')
                            if len(cells) > td_index >= 0:
                                eps_text = cells[td_index].get_text(strip=True)
                                if eps_text == '－':
                                    if verbose:
                                        print(f"  ⊘ Skipping {period}: EPS is '－'")
                                    continue
                                eps_value = KabutanAPI._extract_number(eps_text)
                                if eps_value is not None:
                                    if verbose:
                                        print(f"  ✓ Successfully retrieved EPS: {eps_value} ({period} - Actual)")
                                    return eps_value

            if verbose:
                print(f"  ✗ Failed to find EPS data")
            return None

        except Exception as e:
            if verbose:
                print(f"  ✗ Kabutan error: {e}")
            return None

    @staticmethod
    def get_dividend(code: str, verbose: bool = False) -> Optional[float]:
        """
        Get revised dividend per share (修正1株配) from Kabutan

        Args:
            code: Stock code (4-digit, e.g., "7203")
            verbose: Display detailed logs

        Returns:
            Dividend per share value or None if unable to retrieve
        """
        if verbose:
            print(f"Retrieving dividend from Kabutan: {code}")

        # Get finance page
        soup = KabutanAPI._get_page_content(code, page_type='finance')
        if not soup:
            if verbose:
                print(f"  ✗ Failed to retrieve finance page")
            return None

        try:
            # Look for tables with "修正1株配" header
            tables = soup.find_all('table')
            for table in tables:
                # Find header row
                headers = table.find_all('th', scope='col')
                header_texts = [h.get_text(strip=True).replace('\n', '').replace(' ', '')
                               for h in headers]

                # Check if this table has "修正1株配" column
                div_col_index = None
                for i, text in enumerate(header_texts):
                    if '修正1株配' in text:
                        div_col_index = i
                        break

                if div_col_index is not None:
                    # Adjust index: first column is th (決算期), so td indices are shifted by -1
                    td_index = div_col_index - 1

                    tbody = table.find('tbody')
                    if tbody:
                        data_rows = tbody.find_all('tr')

                        # Step 1: Try to find company forecast (予) first
                        for row in reversed(data_rows):
                            if row.find('th', scope='row') is None:
                                continue

                            row_th = row.find('th', scope='row')
                            if not row_th or 'oc_btn' in str(row.get('class', [])):
                                continue

                            period = row_th.get_text(strip=True)

                            # Only look for forecast data (marked with "予")
                            if '予' not in period:
                                continue

                            # Skip comparison rows
                            if '前期比' in period or '前年同期比' in period or '同期比' in period:
                                continue

                            cells = row.find_all('td')
                            if len(cells) > td_index >= 0:
                                div_text = cells[td_index].get_text(strip=True)
                                # Check if forecast data is available
                                if div_text == '－':
                                    if verbose:
                                        print(f"  ⊘ Skipping {period}: Forecast dividend is '－'")
                                    continue
                                div_value = KabutanAPI._extract_number(div_text)
                                if div_value is not None:
                                    if verbose:
                                        print(f"  ✓ Successfully retrieved dividend: {div_value} ({period} - Forecast)")
                                    return div_value

                        # Step 2: Fallback to actual results if forecast not found
                        if verbose:
                            print(f"  → Forecast not available, falling back to actual results")

                        for row in reversed(data_rows):
                            if row.find('th', scope='row') is None:
                                continue

                            row_th = row.find('th', scope='row')
                            if not row_th or 'oc_btn' in str(row.get('class', [])):
                                continue

                            period = row_th.get_text(strip=True)

                            # Skip forecast data
                            if '予' in period:
                                continue

                            # Skip comparison rows
                            if '前期比' in period or '前年同期比' in period or '同期比' in period:
                                if verbose:
                                    print(f"  ⊘ Skipping {period}: Comparison data")
                                continue

                            cells = row.find_all('td')
                            if len(cells) > td_index >= 0:
                                div_text = cells[td_index].get_text(strip=True)
                                if div_text == '－':
                                    if verbose:
                                        print(f"  ⊘ Skipping {period}: Dividend is '－'")
                                    continue
                                div_value = KabutanAPI._extract_number(div_text)
                                if div_value is not None:
                                    if verbose:
                                        print(f"  ✓ Successfully retrieved dividend: {div_value} ({period} - Actual)")
                                    return div_value

            if verbose:
                print(f"  ✗ Failed to find dividend data")
            return None

        except Exception as e:
            if verbose:
                print(f"  ✗ Kabutan error: {e}")
            return None

    @staticmethod
    def get_stock_info(code: str, verbose: bool = False) -> Optional[Dict]:
        """
        Get comprehensive stock information from Kabutan

        Args:
            code: Stock code (4-digit, e.g., "7203")
            verbose: Display detailed logs

        Returns:
            Dictionary containing EPS and dividend, or None if unable to retrieve
        """
        eps = KabutanAPI.get_eps(code, verbose=verbose)
        dividend = KabutanAPI.get_dividend(code, verbose=verbose)

        if eps is None and dividend is None:
            return None

        return {
            'code': code.replace('.T', ''),
            'eps': eps,
            'dividend': dividend,
        }
