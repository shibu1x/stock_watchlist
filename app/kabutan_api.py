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
    def _get_finance_value(soup: BeautifulSoup, column_name: str, label: str,
                           verbose: bool = False) -> Optional[float]:
        """
        Extract a single value from a Kabutan finance table column.

        Tries forecast (予) rows first, falls back to actual results.

        Args:
            soup: BeautifulSoup object of the finance page
            column_name: Column header to search for (e.g., '修正1株益')
            label: Human-readable label for log messages (e.g., 'EPS')
            verbose: Display detailed logs

        Returns:
            Numeric value or None if not found
        """
        try:
            for table in soup.find_all('table'):
                headers = table.find_all('th', scope='col')
                header_texts = [h.get_text(strip=True).replace('\n', '').replace(' ', '')
                                for h in headers]

                col_index = next((i for i, t in enumerate(header_texts) if column_name in t), None)
                if col_index is None:
                    continue

                # Adjust index: first column is th (決算期), so td indices are shifted by -1
                td_index = col_index - 1

                tbody = table.find('tbody')
                if not tbody:
                    continue

                data_rows = tbody.find_all('tr')

                # Two-pass: try forecast (予) first, then fall back to actual results
                for forecast_only in (True, False):
                    if not forecast_only and verbose:
                        print(f"  → Forecast not available, falling back to actual results")

                    for row in reversed(data_rows):
                        row_th = row.find('th', scope='row')
                        if not row_th or 'oc_btn' in str(row.get('class', [])):
                            continue

                        period = row_th.get_text(strip=True)
                        is_forecast = '予' in period

                        if forecast_only != is_forecast:
                            continue

                        # Skip comparison rows
                        if '前期比' in period or '前年同期比' in period or '同期比' in period:
                            if verbose and not forecast_only:
                                print(f"  ⊘ Skipping {period}: Comparison data")
                            continue

                        cells = row.find_all('td')
                        if len(cells) > td_index >= 0:
                            cell_text = cells[td_index].get_text(strip=True)
                            if cell_text == '－':
                                if verbose:
                                    kind = 'Forecast ' if forecast_only else ''
                                    print(f"  ⊘ Skipping {period}: {kind}{label} is '－'")
                                continue
                            value = KabutanAPI._extract_number(cell_text)
                            if value is not None:
                                if verbose:
                                    kind = 'Forecast' if forecast_only else 'Actual'
                                    print(f"  ✓ Successfully retrieved {label}: {value} ({period} - {kind})")
                                return value

        except Exception as e:
            if verbose:
                print(f"  ✗ Kabutan error: {e}")

        if verbose:
            print(f"  ✗ Failed to find {label} data")
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
        soup = KabutanAPI._get_page_content(code, page_type='finance')
        if not soup:
            if verbose:
                print(f"  ✗ Failed to retrieve finance page")
            return None
        return KabutanAPI._get_finance_value(soup, '修正1株益', 'EPS', verbose)

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
        soup = KabutanAPI._get_page_content(code, page_type='finance')
        if not soup:
            if verbose:
                print(f"  ✗ Failed to retrieve finance page")
            return None
        return KabutanAPI._get_finance_value(soup, '修正1株配', 'dividend', verbose)

    @staticmethod
    def get_stock_info(code: str, verbose: bool = False) -> Optional[Dict]:
        """
        Get comprehensive stock information from Kabutan

        Fetches the finance page once and extracts both EPS and dividend.

        Args:
            code: Stock code (4-digit, e.g., "7203")
            verbose: Display detailed logs

        Returns:
            Dictionary containing EPS and dividend, or None if unable to retrieve
        """
        if verbose:
            print(f"Retrieving EPS and dividend from Kabutan: {code}")
        soup = KabutanAPI._get_page_content(code, page_type='finance')
        if not soup:
            if verbose:
                print(f"  ✗ Failed to retrieve finance page")
            return None

        eps = KabutanAPI._get_finance_value(soup, '修正1株益', 'EPS', verbose)
        dividend = KabutanAPI._get_finance_value(soup, '修正1株配', 'dividend', verbose)

        if eps is None and dividend is None:
            return None

        return {
            'code': code.replace('.T', ''),
            'eps': eps,
            'dividend': dividend,
        }
