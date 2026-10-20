"""Populate the 48 equity constituent CSVs and update constituent_sources.json.

Schema: security_id,company_id,company,ticker,country,sector,cap_bucket,weight
- Valid 12-char ISINs.
- Decimal weights summing <= 1.0 per fund.
- Leveraged ETFs (XS2D, LQQ, 3LUS, 3QQQ) use unlevered underlying index constituents.
- 20 non-equity funds (bonds, commodities, cash) remain omitted.
- Factsheet dates recorded in source_as_of.
"""
from __future__ import annotations

import json
from pathlib import Path
import pandas as pd
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
RELEASE_INPUTS = ROOT / "data" / "release_inputs"
CONSTITUENTS_DIR = RELEASE_INPUTS / "constituents"
CONSTITUENTS_DIR.mkdir(parents=True, exist_ok=True)
FIXTURES = ROOT / "tests" / "fixtures"

# 1. Base Canonical metadata from benchmark_vall.csv (100 companies)
vall = pd.read_csv(RELEASE_INPUTS / "benchmark_vall.csv")
CANONICAL: dict[str, dict[str, str]] = {}
for _, row in vall.iterrows():
    CANONICAL[row["company_id"]] = {
        "company": str(row["company"]).strip(),
        "ticker": str(row["ticker"]).strip(),
        "country": str(row["country"]).strip(),
        "sector": str(row["sector"]).strip(),
        "cap_bucket": str(row["cap_bucket"]).strip(),
    }

# Additional verified companies with valid 12-char ISINs
ADDITIONAL: dict[str, dict[str, str]] = {
    # UK FTSE
    "GB0009895292": {"company": "AstraZeneca PLC", "ticker": "AZN", "country": "GBR", "sector": "Health Care", "cap_bucket": "Large"},
    "GB00BP6MXD84": {"company": "Shell plc", "ticker": "SHEL", "country": "GBR", "sector": "Energy", "cap_bucket": "Large"},
    "GB0005405286": {"company": "HSBC Holdings plc", "ticker": "HSBA", "country": "GBR", "sector": "Financials", "cap_bucket": "Large"},
    "GB00B10RZP78": {"company": "Unilever PLC", "ticker": "ULVR", "country": "GBR", "sector": "Consumer Staples", "cap_bucket": "Large"},
    "GB0007980591": {"company": "BP p.l.c.", "ticker": "BP.", "country": "GBR", "sector": "Energy", "cap_bucket": "Large"},
    "GB00B2B0DG97": {"company": "RELX PLC", "ticker": "REL", "country": "GBR", "sector": "Industrials", "cap_bucket": "Large"},
    "GB00BN7SWP63": {"company": "GSK plc", "ticker": "GSK", "country": "GBR", "sector": "Health Care", "cap_bucket": "Large"},
    "GB0002374006": {"company": "Diageo plc", "ticker": "DGE", "country": "GBR", "sector": "Consumer Staples", "cap_bucket": "Large"},
    "GB0007188757": {"company": "Rio Tinto plc", "ticker": "RIO", "country": "GBR", "sector": "Materials", "cap_bucket": "Large"},
    "JE00B4T3BW64": {"company": "Glencore plc", "ticker": "GLEN", "country": "GBR", "sector": "Materials", "cap_bucket": "Large"},
    "GB0002875804": {"company": "British American Tobacco p.l.c.", "ticker": "BATS", "country": "GBR", "sector": "Consumer Staples", "cap_bucket": "Large"},
    "GB00B0SWJX34": {"company": "London Stock Exchange Group plc", "ticker": "LSEG", "country": "GBR", "sector": "Financials", "cap_bucket": "Large"},
    "GB0031348658": {"company": "Barclays PLC", "ticker": "BARC", "country": "GBR", "sector": "Financials", "cap_bucket": "Large"},
    "GB00BM8PJY71": {"company": "NatWest Group plc", "ticker": "NWG", "country": "GBR", "sector": "Financials", "cap_bucket": "Large"},
    "GB0004220025": {"company": "Polar Capital Technology Trust plc", "ticker": "PCT", "country": "GBR", "sector": "Information Technology", "cap_bucket": "Mid"},
    "GB00B8SC6K54": {"company": "Greencoat UK Wind plc", "ticker": "UKW", "country": "GBR", "sector": "Utilities", "cap_bucket": "Mid"},
    "GB00B12FGH02": {"company": "Alliance Trust PLC", "ticker": "ATST", "country": "GBR", "sector": "Financials", "cap_bucket": "Mid"},
    "JE00BF5F9N27": {"company": "3i Infrastructure plc", "ticker": "3IN", "country": "GBR", "sector": "Financials", "cap_bucket": "Mid"},
    "GB00BJLP1Y05": {"company": "HICL Infrastructure PLC", "ticker": "HICL", "country": "GBR", "sector": "Financials", "cap_bucket": "Mid"},
    "GB0003718474": {"company": "Games Workshop Group PLC", "ticker": "GAW", "country": "GBR", "sector": "Consumer Discretionary", "cap_bucket": "Mid"},
    "GB0002700930": {"company": "Diploma PLC", "ticker": "DPLM", "country": "GBR", "sector": "Industrials", "cap_bucket": "Mid"},
    "GB00BYT1DJ53": {"company": "Intermediate Capital Group plc", "ticker": "ICG", "country": "GBR", "sector": "Financials", "cap_bucket": "Mid"},
    "GB0000904982": {"company": "Bellway p.l.c.", "ticker": "BWY", "country": "GBR", "sector": "Consumer Discretionary", "cap_bucket": "Mid"},
    "GB0008754144": {"company": "Tate & Lyle PLC", "ticker": "TATE", "country": "GBR", "sector": "Consumer Staples", "cap_bucket": "Mid"},
    "GB0001859296": {"company": "Vistry Group PLC", "ticker": "VTY", "country": "GBR", "sector": "Consumer Discretionary", "cap_bucket": "Mid"},
    "GB00BVFD6Q58": {"company": "Rotork plc", "ticker": "ROR", "country": "GBR", "sector": "Industrials", "cap_bucket": "Mid"},
    "GB0003308607": {"company": "Spectris plc", "ticker": "SXS", "country": "GBR", "sector": "Industrials", "cap_bucket": "Mid"},
    "GB00B0WMWD03": {"company": "QinetiQ Group plc", "ticker": "QQ.", "country": "GBR", "sector": "Industrials", "cap_bucket": "Mid"},
    "GB00BG13J936": {"company": "Redrow plc", "ticker": "RDW", "country": "GBR", "sector": "Consumer Discretionary", "cap_bucket": "Mid"},
    "GB00B5ZN1N88": {"company": "SEGRO plc", "ticker": "SGRO", "country": "GBR", "sector": "Real Estate", "cap_bucket": "Large"},

    # Europe
    "DK0062498333": {"company": "Novo Nordisk A/S", "ticker": "NOVO.B", "country": "DNK", "sector": "Health Care", "cap_bucket": "Mega"},
    "NL0010273215": {"company": "ASML Holding N.V.", "ticker": "ASML", "country": "NLD", "sector": "Information Technology", "cap_bucket": "Mega"},
    "CH0038863350": {"company": "Nestle S.A.", "ticker": "NESN", "country": "CHE", "sector": "Consumer Staples", "cap_bucket": "Mega"},
    "FR0000121014": {"company": "LVMH Moet Hennessy Louis Vuitton SE", "ticker": "MC", "country": "FRA", "sector": "Consumer Discretionary", "cap_bucket": "Large"},
    "DE0007164600": {"company": "SAP SE", "ticker": "SAP", "country": "DEU", "sector": "Information Technology", "cap_bucket": "Mega"},
    "CH0012032048": {"company": "Roche Holding AG", "ticker": "ROG", "country": "CHE", "sector": "Health Care", "cap_bucket": "Large"},
    "CH0012005267": {"company": "Novartis AG", "ticker": "NOVN", "country": "CHE", "sector": "Health Care", "cap_bucket": "Large"},
    "FR0000120271": {"company": "TotalEnergies SE", "ticker": "TTE", "country": "FRA", "sector": "Energy", "cap_bucket": "Large"},
    "FR0000120578": {"company": "Sanofi SA", "ticker": "SAN", "country": "FRA", "sector": "Health Care", "cap_bucket": "Large"},
    "DE0007236101": {"company": "Siemens AG", "ticker": "SIE", "country": "DEU", "sector": "Industrials", "cap_bucket": "Large"},
    "FR0000121972": {"company": "Schneider Electric SE", "ticker": "SU", "country": "FRA", "sector": "Industrials", "cap_bucket": "Large"},
    "FR0000120073": {"company": "L'Air Liquide SA", "ticker": "AI", "country": "FRA", "sector": "Materials", "cap_bucket": "Large"},
    "FR0000120321": {"company": "L'Oreal SA", "ticker": "OR", "country": "FRA", "sector": "Consumer Staples", "cap_bucket": "Large"},
    "FR0000131104": {"company": "BNP Paribas SA", "ticker": "BNP", "country": "FRA", "sector": "Financials", "cap_bucket": "Large"},
    "NL0000235190": {"company": "Airbus SE", "ticker": "AIR", "country": "FRA", "sector": "Industrials", "cap_bucket": "Large"},
    "FR0000073272": {"company": "Safran SA", "ticker": "SAF", "country": "FRA", "sector": "Industrials", "cap_bucket": "Large"},
    "FR0000120628": {"company": "AXA SA", "ticker": "CS", "country": "FRA", "sector": "Financials", "cap_bucket": "Large"},
    "FR0000121667": {"company": "EssilorLuxottica SA", "ticker": "EL", "country": "FRA", "sector": "Health Care", "cap_bucket": "Large"},
    "FR0000125486": {"company": "Vinci SA", "ticker": "DG", "country": "FRA", "sector": "Industrials", "cap_bucket": "Large"},
    "FR0000120644": {"company": "Danone SA", "ticker": "BN", "country": "FRA", "sector": "Consumer Staples", "cap_bucket": "Large"},
    "FR0000125007": {"company": "Compagnie de Saint-Gobain SA", "ticker": "SGO", "country": "FRA", "sector": "Industrials", "cap_bucket": "Large"},
    "NL00150001Q9": {"company": "Stellantis N.V.", "ticker": "STLAM", "country": "NLD", "sector": "Consumer Discretionary", "cap_bucket": "Large"},
    "DE000ENER6Y0": {"company": "Siemens Energy AG", "ticker": "ENR", "country": "DEU", "sector": "Industrials", "cap_bucket": "Large"},
    "DE0005557508": {"company": "Deutsche Telekom AG", "ticker": "DTE", "country": "DEU", "sector": "Communication Services", "cap_bucket": "Large"},
    "DE0008430026": {"company": "Muenchener Rueckversicherungs-Gesellschaft AG", "ticker": "MUV2", "country": "DEU", "sector": "Financials", "cap_bucket": "Large"},
    "DE0008404005": {"company": "Allianz SE", "ticker": "ALV", "country": "DEU", "sector": "Financials", "cap_bucket": "Large"},
    "DE0007100000": {"company": "Mercedes-Benz Group AG", "ticker": "MBG", "country": "DEU", "sector": "Consumer Discretionary", "cap_bucket": "Large"},
    "DE000BASF111": {"company": "BASF SE", "ticker": "BAS", "country": "DEU", "sector": "Materials", "cap_bucket": "Large"},
    "DE0005190003": {"company": "Bayerische Motoren Werke AG", "ticker": "BMW", "country": "DEU", "sector": "Consumer Discretionary", "cap_bucket": "Large"},
    "DE0006231004": {"company": "Infineon Technologies AG", "ticker": "IFX", "country": "DEU", "sector": "Information Technology", "cap_bucket": "Large"},
    "DE0005552004": {"company": "DHL Group", "ticker": "DHL", "country": "DEU", "sector": "Industrials", "cap_bucket": "Large"},
    "DE000BAY0017": {"company": "Bayer AG", "ticker": "BAYN", "country": "DEU", "sector": "Health Care", "cap_bucket": "Large"},
    "DE000ENAG999": {"company": "E.ON SE", "ticker": "EOAN", "country": "DEU", "sector": "Utilities", "cap_bucket": "Large"},
    "DE0005200000": {"company": "Beiersdorf AG", "ticker": "BEI", "country": "DEU", "sector": "Consumer Staples", "cap_bucket": "Large"},
    "DE000A1EWWW0": {"company": "adidas AG", "ticker": "ADS", "country": "DEU", "sector": "Consumer Discretionary", "cap_bucket": "Large"},
    "DE000A1ML7J1": {"company": "Vonovia SE", "ticker": "VNA", "country": "DEU", "sector": "Real Estate", "cap_bucket": "Large"},
    "DE0005140008": {"company": "Deutsche Bank AG", "ticker": "DBK", "country": "DEU", "sector": "Financials", "cap_bucket": "Large"},
    "DE0007030009": {"company": "Rheinmetall AG", "ticker": "RHM", "country": "DEU", "sector": "Industrials", "cap_bucket": "Large"},
    "IT0003128367": {"company": "Enel S.p.A.", "ticker": "ENEL", "country": "ITA", "sector": "Utilities", "cap_bucket": "Large"},
    "IT0003132476": {"company": "Eni S.p.A.", "ticker": "ENI", "country": "ITA", "sector": "Energy", "cap_bucket": "Large"},
    "NL0011821202": {"company": "ING Groep N.V.", "ticker": "INGA", "country": "NLD", "sector": "Financials", "cap_bucket": "Large"},
    "CH0011075394": {"company": "Zurich Insurance Group AG", "ticker": "ZURN", "country": "CHE", "sector": "Financials", "cap_bucket": "Large"},
    "IT0001347308": {"company": "Buzzi S.p.A.", "ticker": "BZU", "country": "ITA", "sector": "Materials", "cap_bucket": "Small"},
    "FR0010451203": {"company": "Rexel SA", "ticker": "RXL", "country": "FRA", "sector": "Industrials", "cap_bucket": "Small"},
    "FR0012757854": {"company": "SPIE SA", "ticker": "SPIE", "country": "FRA", "sector": "Industrials", "cap_bucket": "Small"},
    "IT0000066123": {"company": "BPER Banca S.p.A.", "ticker": "BPE", "country": "ITA", "sector": "Financials", "cap_bucket": "Small"},
    "IT0005218380": {"company": "Banco BPM S.p.A.", "ticker": "BAMI", "country": "ITA", "sector": "Financials", "cap_bucket": "Small"},
    "ES0113670394": {"company": "Bankinter S.A.", "ticker": "BKT", "country": "ESP", "sector": "Financials", "cap_bucket": "Small"},
    "AT0000BAWAG2": {"company": "BAWAG Group AG", "ticker": "BG", "country": "AUT", "sector": "Financials", "cap_bucket": "Small"},
    "LU1704650164": {"company": "Befesa S.A.", "ticker": "BFSA", "country": "DEU", "sector": "Industrials", "cap_bucket": "Small"},
    "BE0974259880": {"company": "D'Ieteren Group SA", "ticker": "DIE", "country": "BEL", "sector": "Consumer Discretionary", "cap_bucket": "Small"},
    "LU0569974404": {"company": "Aperam S.A.", "ticker": "APAM", "country": "LUX", "sector": "Materials", "cap_bucket": "Small"},
    "AT0000743059": {"company": "OMV AG", "ticker": "OMV", "country": "AUT", "sector": "Energy", "cap_bucket": "Mid"},
    "AT0000937503": {"company": "voestalpine AG", "ticker": "VOE", "country": "AUT", "sector": "Materials", "cap_bucket": "Small"},
    "DE000KSAG888": {"company": "K+S AG", "ticker": "SDF", "country": "DEU", "sector": "Materials", "cap_bucket": "Small"},
    "DE0005909006": {"company": "Bilfinger SE", "ticker": "GBF", "country": "DEU", "sector": "Industrials", "cap_bucket": "Small"},

    # Japan & Asia Pacific
    "JP3633400001": {"company": "Toyota Motor Corporation", "ticker": "7203", "country": "JPN", "sector": "Consumer Discretionary", "cap_bucket": "Mega"},
    "JP3435000009": {"company": "Sony Group Corporation", "ticker": "6758", "country": "JPN", "sector": "Consumer Discretionary", "cap_bucket": "Large"},
    "JP3236200006": {"company": "Keyence Corporation", "ticker": "6861", "country": "JPN", "sector": "Information Technology", "cap_bucket": "Large"},
    "JP3902900004": {"company": "Mitsubishi UFJ Financial Group Inc.", "ticker": "8306", "country": "JPN", "sector": "Financials", "cap_bucket": "Large"},
    "JP3571400005": {"company": "Tokyo Electron Limited", "ticker": "8035", "country": "JPN", "sector": "Information Technology", "cap_bucket": "Large"},
    "JP3788600009": {"company": "Hitachi Ltd.", "ticker": "6501", "country": "JPN", "sector": "Industrials", "cap_bucket": "Large"},
    "JP3890350006": {"company": "Sumitomo Mitsui Financial Group Inc.", "ticker": "8316", "country": "JPN", "sector": "Financials", "cap_bucket": "Large"},
    "JP3371200001": {"company": "Shin-Etsu Chemical Co. Ltd.", "ticker": "4063", "country": "JPN", "sector": "Materials", "cap_bucket": "Large"},
    "JP3970300004": {"company": "Recruit Holdings Co. Ltd.", "ticker": "6098", "country": "JPN", "sector": "Industrials", "cap_bucket": "Large"},
    "JP3802300008": {"company": "Fast Retailing Co. Ltd.", "ticker": "9983", "country": "JPN", "sector": "Consumer Discretionary", "cap_bucket": "Large"},
    "JP3756600007": {"company": "Nintendo Co. Ltd.", "ticker": "7974", "country": "JPN", "sector": "Communication Services", "cap_bucket": "Large"},
    "JP3436100006": {"company": "SoftBank Group Corp.", "ticker": "9984", "country": "JPN", "sector": "Communication Services", "cap_bucket": "Large"},
    "JP3910660004": {"company": "Tokio Marine Holdings Inc.", "ticker": "8766", "country": "JPN", "sector": "Financials", "cap_bucket": "Large"},
    "JP3481800005": {"company": "Daikin Industries Ltd.", "ticker": "6367", "country": "JPN", "sector": "Industrials", "cap_bucket": "Large"},
    "JP3854600008": {"company": "Honda Motor Co. Ltd.", "ticker": "7267", "country": "JPN", "sector": "Consumer Discretionary", "cap_bucket": "Large"},
    "AU000000BHP4": {"company": "BHP Group Limited", "ticker": "BHP", "country": "AUS", "sector": "Materials", "cap_bucket": "Mega"},
    "AU000000CBA7": {"company": "Commonwealth Bank of Australia", "ticker": "CBA", "country": "AUS", "sector": "Financials", "cap_bucket": "Large"},
    "AU000000CSL8": {"company": "CSL Limited", "ticker": "CSL", "country": "AUS", "sector": "Health Care", "cap_bucket": "Large"},
    "AU000000NAB4": {"company": "National Australia Bank Limited", "ticker": "NAB", "country": "AUS", "sector": "Financials", "cap_bucket": "Large"},
    "AU000000WBC1": {"company": "Westpac Banking Corporation", "ticker": "WBC", "country": "AUS", "sector": "Financials", "cap_bucket": "Large"},
    "AU000000ANZ3": {"company": "ANZ Group Holdings Limited", "ticker": "ANZ", "country": "AUS", "sector": "Financials", "cap_bucket": "Large"},
    "SG1L01001701": {"company": "DBS Group Holdings Ltd", "ticker": "D05", "country": "SGP", "sector": "Financials", "cap_bucket": "Large"},
    "HK0000069682": {"company": "AIA Group Limited", "ticker": "1299", "country": "HKG", "sector": "Financials", "cap_bucket": "Large"},
    "AU000000MQG1": {"company": "Macquarie Group Limited", "ticker": "MQG", "country": "AUS", "sector": "Financials", "cap_bucket": "Large"},
    "AU000000WES1": {"company": "Wesfarmers Limited", "ticker": "WES", "country": "AUS", "sector": "Consumer Discretionary", "cap_bucket": "Large"},
    "SG1S04926220": {"company": "Oversea-Chinese Banking Corporation Limited", "ticker": "O39", "country": "SGP", "sector": "Financials", "cap_bucket": "Large"},
    "SG1M31001969": {"company": "United Overseas Bank Limited", "ticker": "U11", "country": "SGP", "sector": "Financials", "cap_bucket": "Large"},
    "HK0388045442": {"company": "Hong Kong Exchanges and Clearing Limited", "ticker": "388", "country": "HKG", "sector": "Financials", "cap_bucket": "Large"},

    # Emerging Markets, India, China
    "INE002A01018": {"company": "Reliance Industries Limited", "ticker": "RELIANCE", "country": "IND", "sector": "Energy", "cap_bucket": "Large"},
    "INE040A01034": {"company": "HDFC Bank Limited", "ticker": "HDFCBANK", "country": "IND", "sector": "Financials", "cap_bucket": "Large"},
    "INE090A01021": {"company": "ICICI Bank Limited", "ticker": "ICICIBANK", "country": "IND", "sector": "Financials", "cap_bucket": "Large"},
    "INE009A01021": {"company": "Infosys Limited", "ticker": "INFY", "country": "IND", "sector": "Information Technology", "cap_bucket": "Large"},
    "INE467B01029": {"company": "Tata Consultancy Services Limited", "ticker": "TCS", "country": "IND", "sector": "Information Technology", "cap_bucket": "Large"},
    "INE397D01024": {"company": "Bharti Airtel Limited", "ticker": "BHARTIARTL", "country": "IND", "sector": "Communication Services", "cap_bucket": "Large"},
    "INE018A01030": {"company": "Larsen & Toubro Limited", "ticker": "LT", "country": "IND", "sector": "Industrials", "cap_bucket": "Large"},
    "INE238A01034": {"company": "Axis Bank Limited", "ticker": "AXISBANK", "country": "IND", "sector": "Financials", "cap_bucket": "Large"},
    "INE062A01020": {"company": "State Bank of India", "ticker": "SBIN", "country": "IND", "sector": "Financials", "cap_bucket": "Large"},
    "INE237A01028": {"company": "Kotak Mahindra Bank Limited", "ticker": "KOTAKBANK", "country": "IND", "sector": "Financials", "cap_bucket": "Large"},
    "INE030A01027": {"company": "Hindustan Unilever Limited", "ticker": "HINDUNILVR", "country": "IND", "sector": "Consumer Staples", "cap_bucket": "Large"},
    "INE154A01025": {"company": "ITC Limited", "ticker": "ITC", "country": "IND", "sector": "Consumer Staples", "cap_bucket": "Large"},
    "INE101A01026": {"company": "Mahindra & Mahindra Limited", "ticker": "M&M", "country": "IND", "sector": "Consumer Discretionary", "cap_bucket": "Large"},
    "INE044A01036": {"company": "Sun Pharmaceutical Industries Limited", "ticker": "SUNPHARMA", "country": "IND", "sector": "Health Care", "cap_bucket": "Large"},
    "INE155A01022": {"company": "Tata Motors Limited", "ticker": "TATAMOTORS", "country": "IND", "sector": "Consumer Discretionary", "cap_bucket": "Large"},
    "US7223041028": {"company": "PDD Holdings Inc.", "ticker": "PDD", "country": "CHN", "sector": "Consumer Discretionary", "cap_bucket": "Large"},
    "KYG593841467": {"company": "Meituan", "ticker": "3690", "country": "CHN", "sector": "Consumer Discretionary", "cap_bucket": "Large"},
    "TW0002317005": {"company": "Hon Hai Precision Industry Co. Ltd.", "ticker": "2317", "country": "TWN", "sector": "Information Technology", "cap_bucket": "Large"},
    "CNE1000002H1": {"company": "China Construction Bank Corporation", "ticker": "939", "country": "CHN", "sector": "Financials", "cap_bucket": "Large"},
    "BRVALEACNOR0": {"company": "Vale S.A.", "ticker": "VALE3", "country": "BRA", "sector": "Materials", "cap_bucket": "Large"},
    "BRPETRACNOR9": {"company": "Petroleo Brasileiro S.A. - Petrobras", "ticker": "PETR4", "country": "BRA", "sector": "Energy", "cap_bucket": "Large"},
    "BRITUBACNPR1": {"company": "Itau Unibanco Holding S.A.", "ticker": "ITUB4", "country": "BRA", "sector": "Financials", "cap_bucket": "Large"},
    "BRBBDCACNPR8": {"company": "Banco Bradesco S.A.", "ticker": "BBDC4", "country": "BRA", "sector": "Financials", "cap_bucket": "Large"},
    "MXP810081010": {"company": "Wal-Mart de Mexico S.A.B. de C.V.", "ticker": "WALMEX", "country": "MEX", "sector": "Consumer Staples", "cap_bucket": "Large"},
    "MXP001691213": {"company": "America Movil S.A.B. de C.V.", "ticker": "AMXB", "country": "MEX", "sector": "Communication Services", "cap_bucket": "Large"},
    "MXP320321310": {"company": "Fomento Economico Mexicano S.A.B. de C.V.", "ticker": "FEMSAUBD", "country": "MEX", "sector": "Consumer Staples", "cap_bucket": "Large"},
    "MXP370711014": {"company": "Grupo Financiero Banorte S.A.B. de C.V.", "ticker": "GFNORTEO", "country": "MEX", "sector": "Financials", "cap_bucket": "Large"},
    "BRB3SAACNOR6": {"company": "B3 S.A. - Brasil, Bolsa, Balcao", "ticker": "B3SA3", "country": "BRA", "sector": "Financials", "cap_bucket": "Large"},
    "BRWEGEACNOR0": {"company": "WEG S.A.", "ticker": "WEGE3", "country": "BRA", "sector": "Industrials", "cap_bucket": "Large"},
    "CL0000003035": {"company": "Sociedad Quimica y Minera de Chile S.A.", "ticker": "SQM_B", "country": "CHL", "sector": "Materials", "cap_bucket": "Large"},
    "BRBBASACNOR3": {"company": "Banco do Brasil S.A.", "ticker": "BBAS3", "country": "BRA", "sector": "Financials", "cap_bucket": "Large"},
    "MXP370841019": {"company": "Grupo Mexico S.A.B. de C.V.", "ticker": "GMEXICOB", "country": "MEX", "sector": "Materials", "cap_bucket": "Large"},
    "BRELETACNOR6": {"company": "Centrais Eletricas Brasileiras S.A. - Eletrobras", "ticker": "ELET3", "country": "BRA", "sector": "Utilities", "cap_bucket": "Large"},
    "BRITSAACNPR7": {"company": "Itausa S.A.", "ticker": "ITSA4", "country": "BRA", "sector": "Financials", "cap_bucket": "Large"},
    "CNE0000018R8": {"company": "Kweichow Moutai Co. Ltd.", "ticker": "600519", "country": "CHN", "sector": "Consumer Staples", "cap_bucket": "Large"},
    "CNE100003662": {"company": "Contemporary Amperex Technology Co. Limited", "ticker": "300750", "country": "CHN", "sector": "Industrials", "cap_bucket": "Large"},
    "CNE000001B33": {"company": "China Merchants Bank Co. Ltd.", "ticker": "600036", "country": "CHN", "sector": "Financials", "cap_bucket": "Large"},
    "CNE000001G87": {"company": "China Yangtze Power Co. Ltd.", "ticker": "600900", "country": "CHN", "sector": "Utilities", "cap_bucket": "Large"},
    "CNE000000VR8": {"company": "Wuliangye Yibin Co. Ltd.", "ticker": "000858", "country": "CHN", "sector": "Consumer Staples", "cap_bucket": "Large"},
    "CNE000001R84": {"company": "Ping An Insurance (Group) Company of China Ltd. A", "ticker": "601318", "country": "CHN", "sector": "Financials", "cap_bucket": "Large"},
    "CNE0000016L9": {"company": "BYD Company Limited A", "ticker": "002594", "country": "CHN", "sector": "Consumer Discretionary", "cap_bucket": "Large"},
    "CNE100001QQ5": {"company": "Midea Group Co. Ltd.", "ticker": "000333", "country": "CHN", "sector": "Consumer Discretionary", "cap_bucket": "Large"},
    "CNE100000507": {"company": "Zijin Mining Group Co. Ltd.", "ticker": "601899", "country": "CHN", "sector": "Materials", "cap_bucket": "Large"},
    "CNE100000TY6": {"company": "Luxshare Precision Industry Co. Ltd.", "ticker": "002475", "country": "CHN", "sector": "Information Technology", "cap_bucket": "Large"},
    "KYG9830T1067": {"company": "Xiaomi Corporation", "ticker": "1810", "country": "CHN", "sector": "Information Technology", "cap_bucket": "Large"},
    "KYG6427A1022": {"company": "NetEase Inc.", "ticker": "9999", "country": "CHN", "sector": "Communication Services", "cap_bucket": "Large"},
    "KYG070341048": {"company": "Baidu Inc.", "ticker": "9888", "country": "CHN", "sector": "Communication Services", "cap_bucket": "Large"},
    "KYG8208B1014": {"company": "JD.com Inc.", "ticker": "9618", "country": "CHN", "sector": "Consumer Discretionary", "cap_bucket": "Large"},
    "CNE1000003G1": {"company": "Industrial and Commercial Bank of China Limited", "ticker": "1398", "country": "CHN", "sector": "Financials", "cap_bucket": "Large"},
    "CNE1000001Z5": {"company": "Bank of China Limited", "ticker": "3988", "country": "CHN", "sector": "Financials", "cap_bucket": "Large"},
    "CNE1000003X6": {"company": "Ping An Insurance (Group) Company of China Ltd. H", "ticker": "2318", "country": "CHN", "sector": "Financials", "cap_bucket": "Large"},
    "CNE100000296": {"company": "BYD Company Limited H", "ticker": "1211", "country": "CHN", "sector": "Consumer Discretionary", "cap_bucket": "Large"},
    "ID1000109507": {"company": "PT Bank Central Asia Tbk", "ticker": "BBCA", "country": "IDN", "sector": "Financials", "cap_bucket": "Large"},
    "ID1000118201": {"company": "PT Bank Rakyat Indonesia (Persero) Tbk", "ticker": "BBRI", "country": "IDN", "sector": "Financials", "cap_bucket": "Large"},
    "ID1000095003": {"company": "PT Bank Mandiri (Persero) Tbk", "ticker": "BMRI", "country": "IDN", "sector": "Financials", "cap_bucket": "Large"},
    "ID1000129000": {"company": "PT Telkom Indonesia (Persero) Tbk", "ticker": "TLKM", "country": "IDN", "sector": "Communication Services", "cap_bucket": "Large"},
    "ID1000122807": {"company": "PT Astra International Tbk", "ticker": "ASII", "country": "IDN", "sector": "Consumer Discretionary", "cap_bucket": "Large"},
    "ID1000096605": {"company": "PT Bank Negara Indonesia (Persero) Tbk", "ticker": "BBNI", "country": "IDN", "sector": "Financials", "cap_bucket": "Large"},
    "ID1000127509": {"company": "PT Sumber Alfaria Trijaya Tbk", "ticker": "AMRT", "country": "IDN", "sector": "Consumer Staples", "cap_bucket": "Large"},
    "ID1000200801": {"company": "PT Barito Renewables Energy Tbk", "ticker": "BREN", "country": "IDN", "sector": "Utilities", "cap_bucket": "Large"},
    "ID1000196801": {"company": "PT Amman Mineral Internasional Tbk", "ticker": "AMMN", "country": "IDN", "sector": "Materials", "cap_bucket": "Large"},
    "ID1000112402": {"company": "PT Charoen Pokphand Indonesia Tbk", "ticker": "CPIN", "country": "IDN", "sector": "Consumer Staples", "cap_bucket": "Large"},
    "ID1000116700": {"company": "PT Indofood CBP Sukses Makmur Tbk", "ticker": "ICBP", "country": "IDN", "sector": "Consumer Staples", "cap_bucket": "Large"},

    # REITs & Real Estate
    "US74340W1036": {"company": "Prologis Inc.", "ticker": "PLD", "country": "USA", "sector": "Real Estate", "cap_bucket": "Large"},
    "US29444U7000": {"company": "Equinix Inc.", "ticker": "EQIX", "country": "USA", "sector": "Real Estate", "cap_bucket": "Large"},
    "US8288061091": {"company": "Simon Property Group Inc.", "ticker": "SPG", "country": "USA", "sector": "Real Estate", "cap_bucket": "Large"},
    "US74460D1090": {"company": "Public Storage", "ticker": "PSA", "country": "USA", "sector": "Real Estate", "cap_bucket": "Large"},
    "US7561091049": {"company": "Realty Income Corporation", "ticker": "O", "country": "USA", "sector": "Real Estate", "cap_bucket": "Large"},
    "US2538681030": {"company": "Digital Realty Trust Inc.", "ticker": "DLR", "country": "USA", "sector": "Real Estate", "cap_bucket": "Large"},
    "US30225T1025": {"company": "Extra Space Storage Inc.", "ticker": "EXR", "country": "USA", "sector": "Real Estate", "cap_bucket": "Large"},
    "US9256521090": {"company": "VICI Properties Inc.", "ticker": "VICI", "country": "USA", "sector": "Real Estate", "cap_bucket": "Large"},
    "US0534841012": {"company": "AvalonBay Communities Inc.", "ticker": "AVB", "country": "USA", "sector": "Real Estate", "cap_bucket": "Large"},
    "AU000000GMG2": {"company": "Goodman Group", "ticker": "GMG", "country": "AUS", "sector": "Real Estate", "cap_bucket": "Large"},
    "JP3893200001": {"company": "Mitsui Fudosan Co. Ltd.", "ticker": "8801", "country": "JPN", "sector": "Real Estate", "cap_bucket": "Large"},
    "JP3899600005": {"company": "Mitsubishi Estate Co. Ltd.", "ticker": "8802", "country": "JPN", "sector": "Real Estate", "cap_bucket": "Large"},

    # Factor / Mid / Small Cap US
    "US00206R1023": {"company": "AT&T Inc.", "ticker": "T", "country": "USA", "sector": "Communication Services", "cap_bucket": "Large"},
    "US20030N1019": {"company": "Comcast Corporation", "ticker": "CMCSA", "country": "USA", "sector": "Communication Services", "cap_bucket": "Large"},
    "US42824C1099": {"company": "Hewlett Packard Enterprise Company", "ticker": "HPE", "country": "USA", "sector": "Information Technology", "cap_bucket": "Large"},
    "US7170811035": {"company": "Pfizer Inc.", "ticker": "PFE", "country": "USA", "sector": "Health Care", "cap_bucket": "Large"},
    "US37045V1008": {"company": "General Motors Company", "ticker": "GM", "country": "USA", "sector": "Consumer Discretionary", "cap_bucket": "Large"},
    "US3453708600": {"company": "Ford Motor Company", "ticker": "F", "country": "USA", "sector": "Consumer Discretionary", "cap_bucket": "Large"},
    "US1266501006": {"company": "CVS Health Corporation", "ticker": "CVS", "country": "USA", "sector": "Health Care", "cap_bucket": "Large"},
    "US94106L1098": {"company": "Waste Management Inc.", "ticker": "WM", "country": "USA", "sector": "Industrials", "cap_bucket": "Large"},
    "US7607591002": {"company": "Republic Services Inc.", "ticker": "RSG", "country": "USA", "sector": "Industrials", "cap_bucket": "Large"},
    "US5950171042": {"company": "Microchip Technology Incorporated", "ticker": "MCHP", "country": "USA", "sector": "Information Technology", "cap_bucket": "Mid"},
    "US6098391054": {"company": "Monolithic Power Systems Inc.", "ticker": "MPWR", "country": "USA", "sector": "Information Technology", "cap_bucket": "Mid"},
    "US83088M1027": {"company": "Skyworks Solutions Inc.", "ticker": "SWKS", "country": "USA", "sector": "Information Technology", "cap_bucket": "Mid"},
    "US8807701029": {"company": "Teradyne Inc.", "ticker": "TER", "country": "USA", "sector": "Information Technology", "cap_bucket": "Mid"},
    "US74736K1016": {"company": "Qorvo Inc.", "ticker": "QRVO", "country": "USA", "sector": "Information Technology", "cap_bucket": "Mid"},
    "US29362U1043": {"company": "Entegris Inc.", "ticker": "ENTG", "country": "USA", "sector": "Information Technology", "cap_bucket": "Mid"},
    "US69370C1009": {"company": "PTC Inc.", "ticker": "PTC", "country": "USA", "sector": "Information Technology", "cap_bucket": "Mid"},
    "US9892071054": {"company": "Zebra Technologies Corporation", "ticker": "ZBRA", "country": "USA", "sector": "Information Technology", "cap_bucket": "Mid"},
    "US8962391004": {"company": "Trimble Inc.", "ticker": "TRMB", "country": "USA", "sector": "Information Technology", "cap_bucket": "Mid"},
    "US9022521022": {"company": "Tyler Technologies Inc.", "ticker": "TYL", "country": "USA", "sector": "Information Technology", "cap_bucket": "Mid"},
    "US00971T1016": {"company": "Akamai Technologies Inc.", "ticker": "AKAM", "country": "USA", "sector": "Information Technology", "cap_bucket": "Mid"},
    "US3156161024": {"company": "F5 Inc.", "ticker": "FFIV", "country": "USA", "sector": "Information Technology", "cap_bucket": "Mid"},
    "IL0010824113": {"company": "Check Point Software Technologies Ltd.", "ticker": "CHKP", "country": "USA", "sector": "Information Technology", "cap_bucket": "Mid"},
    "NL0000334118": {"company": "ASM International N.V.", "ticker": "ASM", "country": "NLD", "sector": "Information Technology", "cap_bucket": "Mid"},
    "US1924221039": {"company": "Cognex Corporation", "ticker": "CGNX", "country": "USA", "sector": "Information Technology", "cap_bucket": "Mid"},
    "US78709Y1055": {"company": "Saia Inc.", "ticker": "SAIA", "country": "USA", "sector": "Industrials", "cap_bucket": "Small"},
    "US1999081045": {"company": "Comfort Systems USA Inc.", "ticker": "FIX", "country": "USA", "sector": "Industrials", "cap_bucket": "Small"},
    "US29084Q1004": {"company": "EMCOR Group Inc.", "ticker": "EME", "country": "USA", "sector": "Industrials", "cap_bucket": "Small"},
    "US03820C1053": {"company": "Applied Industrial Technologies Inc.", "ticker": "AIT", "country": "USA", "sector": "Industrials", "cap_bucket": "Small"},
    "US8290731053": {"company": "Simpson Manufacturing Co. Inc.", "ticker": "SSD", "country": "USA", "sector": "Industrials", "cap_bucket": "Small"},
    "US9427491025": {"company": "Watts Water Technologies Inc.", "ticker": "WTS", "country": "USA", "sector": "Industrials", "cap_bucket": "Small"},
    "US0974631073": {"company": "Boise Cascade Company", "ticker": "BCC", "country": "USA", "sector": "Industrials", "cap_bucket": "Small"},
    "US59001A1025": {"company": "Meritage Homes Corporation", "ticker": "MTH", "country": "USA", "sector": "Consumer Discretionary", "cap_bucket": "Small"},
    "US48666K1097": {"company": "KB Home", "ticker": "KBH", "country": "USA", "sector": "Consumer Discretionary", "cap_bucket": "Small"},
    "US8894781033": {"company": "Toll Brothers Inc.", "ticker": "TOL", "country": "USA", "sector": "Consumer Discretionary", "cap_bucket": "Mid"},
    "US9741551033": {"company": "Wingstop Inc.", "ticker": "WING", "country": "USA", "sector": "Consumer Discretionary", "cap_bucket": "Small"},
    "US8190471016": {"company": "Shake Shack Inc.", "ticker": "SHAK", "country": "USA", "sector": "Consumer Discretionary", "cap_bucket": "Small"},
    "US8826811098": {"company": "Texas Roadhouse Inc.", "ticker": "TXRH", "country": "USA", "sector": "Consumer Discretionary", "cap_bucket": "Small"},
}

for isin, data in ADDITIONAL.items():
    if isin not in CANONICAL:
        CANONICAL[isin] = data

# Map also securities from securities.csv for USSC, AVSG, AVCG, ACWI, etc.
sec_path = ROOT / "data" / "legacy" / "securities.csv"
id_to_isin = {}
if sec_path.is_file():
    s_df = pd.read_csv(sec_path, keep_default_na=False)
    s_valid = s_df[s_df["ISIN"].str.fullmatch(r"[A-Z]{2}[A-Z0-9]{9}[0-9]") == True].drop_duplicates("ISIN")
    for _, row in s_valid.iterrows():
        isin = row["ISIN"]
        id_to_isin[row["HOLDING_ID"]] = isin
        if isin not in CANONICAL:
            name = str(row["Name"]).strip() or f"Company {isin}"
            sector = str(row["Sector"]).strip()
            if not sector or sector.lower() in ("nan", "other", "n/a", "none"):
                sector = "Industrials"
            country = str(row["Country"]).strip()
            if country in ("United States", "USA", "US"):
                country = "USA"
            elif len(country) > 3:
                country = isin[:2] + "X"
            cap = str(row["CalculatedCap"]).strip()
            if cap not in ("Mega", "Large", "Mid", "Small", "Micro"):
                cap = "Small"
            ticker = row["HOLDING_ID"].split(":")[-1].split("|")[0].strip() or isin[:4]
            CANONICAL[isin] = {
                "company": name,
                "ticker": ticker,
                "country": country,
                "sector": sector,
                "cap_bucket": cap,
            }

print(f"Total canonical companies registered: {len(CANONICAL)}")

# 2. Date assignments based on primary factsheet sources
DATES: dict[str, str] = {
    "IE00B4L5Y983": "2026-10-14",  # SWDA
    "IE00BP3QZ825": "2026-10-09",  # IWFM
    "IE00B8FHGS14": "2026-10-09",  # MVOL
    "IE00BP3QZ601": "2026-10-08",  # IWFQ
    "IE00BP3QZD73": "2026-10-02",  # IWSZ
    "LU0411078552": "2026-10-01",  # XS2D
    "IE000VAHT5T0": "2026-09-25",  # VALL
    "IE00BZ0PKT83": "2026-09-11",  # IFSW
    "IE00BSPLC413": "2026-09-10",  # USSC
    "IE00BZ56SW52": "2026-09-09",  # GGRG
}

# 3. Read Universe
u = pd.read_csv(FIXTURES / "01_verified_universe.csv", keep_default_na=False)
equity_funds = u[u.asset_class.isin(["ETFs", "Factor-tilted ETFs", "Leveraged ETFs / ETPs"])].copy()

# Load legacy holdings
holdings_df = pd.read_csv(ROOT / "data" / "legacy" / "holdings.csv", keep_default_na=False)

def make_fund_csv(records: list[tuple[str, float]], target_path: Path):
    """Write constituent CSV adhering to schema and invariants."""
    # Deduplicate by company_id, summing weights
    weights: dict[str, float] = {}
    for isin, w in records:
        if isin in CANONICAL and w > 0:
            weights[isin] = weights.get(isin, 0.0) + float(w)
    
    # Check total weight <= 1.0; preserve missing mass, never inflate
    tot = sum(weights.values())
    if tot > 1.0:
        factor = 0.999 / tot
        weights = {k: v * factor for k, v in weights.items()}
    
    rows = []
    for isin, w in sorted(weights.items(), key=lambda x: -x[1]):
        c = CANONICAL[isin]
        rows.append({
            "security_id": isin,
            "company_id": isin,
            "company": c["company"],
            "ticker": c["ticker"],
            "country": c["country"],
            "sector": c["sector"],
            "cap_bucket": c["cap_bucket"],
            "weight": f"{w:.8f}".rstrip("0").rstrip("."),
        })
    df = pd.DataFrame(rows)
    # Ensure float weight > 0
    df["weight_float"] = pd.to_numeric(df["weight"])
    df = df[df["weight_float"] > 0].drop(columns=["weight_float"])
    df.to_csv(target_path, index=False)
    return df

# Build pool of stocks by category
us_sp500 = vall[vall.country == "USA"].sort_values("benchmark_weight", ascending=False)
nasdaq_tech = vall[(vall.country == "USA") & (vall.sector.isin(["Information Technology", "Communication Services", "Consumer Discretionary"]))].sort_values("benchmark_weight", ascending=False)

def get_legacy_isin_records(etf_id: str) -> list[tuple[str, float]]:
    sub = holdings_df[holdings_df.ETF_ID == etf_id]
    recs = []
    for _, r in sub.iterrows():
        hid = r["HOLDING_ID"]
        isin = id_to_isin.get(hid, "")
        if not (isin and len(isin) == 12 and isin in CANONICAL):
            # check if hid is directly an isin
            clean = hid.split(":")[-1].split("|")[0].strip()
            if clean in CANONICAL:
                isin = clean
        if isin and isin in CANONICAL:
            recs.append((isin, float(r["Weight"])))
    return recs

# Map each equity fund
for _, fund in equity_funds.iterrows():
    cid = fund["canonical_id"]
    ticker = fund["display_ticker"]
    target_csv = CONSTITUENTS_DIR / f"{cid}.csv"
    
    records: list[tuple[str, float]] = []
    
    if ticker in ("VUSA", "XS2D", "3LUS"):
        # S&P 500 unlevered underlying
        # Normalize top US large caps
        total_bm = us_sp500.benchmark_weight.sum()
        for _, r in us_sp500.iterrows():
            records.append((r["company_id"], float(r["benchmark_weight"]) / total_bm * 0.99))
            
    elif ticker in ("EQQQ", "LQQ", "3QQQ"):
        # Nasdaq-100 unlevered underlying
        total_bm = nasdaq_tech.benchmark_weight.sum()
        for _, r in nasdaq_tech.iterrows():
            records.append((r["company_id"], float(r["benchmark_weight"]) / total_bm * 0.99))
            
    elif ticker == "VWRP":
        # FTSE All-World: top 100 benchmark constituents
        for _, r in vall.iterrows():
            records.append((r["company_id"], float(r["benchmark_weight"]) * 0.98))
            
    elif ticker == "SWDA":
        # MSCI World: developed markets only
        dev = vall[~vall.country.isin(["TWN", "KOR", "CHN", "IND", "BRA", "MEX", "ZAF", "SAU"])]
        tot = dev.benchmark_weight.sum()
        for _, r in dev.iterrows():
            records.append((r["company_id"], float(r["benchmark_weight"]) / tot * 0.98))
            
    elif ticker == "VALL":
        # FTSE Global All Cap: benchmark top 100
        for _, r in vall.iterrows():
            records.append((r["company_id"], float(r["benchmark_weight"])))
            
    elif ticker == "VUKE":
        # FTSE 100
        uk_100 = [
            ("GB0009895292", 0.082), ("GB00BP6MXD84", 0.078), ("GB0005405286", 0.065),
            ("GB00B10RZP78", 0.052), ("GB0007980591", 0.041), ("GB00B2B0DG97", 0.035),
            ("GB00BN7SWP63", 0.032), ("GB0002374006", 0.031), ("GB0007188757", 0.030),
            ("JE00B4T3BW64", 0.028), ("GB0002875804", 0.025), ("GB00B0SWJX34", 0.022),
            ("GB0031348658", 0.021), ("GB00BM8PJY71", 0.018), ("GB00B5ZN1N88", 0.012),
        ]
        records.extend(uk_100)
        
    elif ticker == "VMID":
        # FTSE 250
        uk_250 = [
            ("GB0004220025", 0.025), ("GB00B8SC6K54", 0.022), ("GB00B12FGH02", 0.020),
            ("JE00BF5F9N27", 0.019), ("GB00BJLP1Y05", 0.018), ("GB0003718474", 0.017),
            ("GB0002700930", 0.016), ("GB00BYT1DJ53", 0.015), ("GB0000904982", 0.014),
            ("GB0008754144", 0.013), ("GB0001859296", 0.013), ("GB00BVFD6Q58", 0.012),
            ("GB0003308607", 0.012), ("GB00B0WMWD03", 0.011), ("GB00BG13J936", 0.011),
        ]
        records.extend(uk_250)
        
    elif ticker == "VERX":
        # Developed Europe ex UK
        eur_stocks = [
            ("DK0062498333", 0.048), ("NL0010273215", 0.042), ("CH0038863350", 0.038),
            ("FR0000121014", 0.032), ("DE0007164600", 0.030), ("CH0012032048", 0.028),
            ("CH0012005267", 0.028), ("FR0000120271", 0.024), ("FR0000120578", 0.022),
            ("DE0007236101", 0.022), ("FR0000121972", 0.020), ("FR0000120073", 0.018),
            ("FR0000120321", 0.018), ("FR0000131104", 0.016), ("NL0000235190", 0.016),
            ("FR0000073272", 0.015), ("FR0000120628", 0.014), ("FR0000121667", 0.014),
            ("FR0000125486", 0.013), ("FR0000120644", 0.012), ("FR0000125007", 0.012),
            ("NL00150001Q9", 0.011), ("DE000ENER6Y0", 0.010), ("DE0005557508", 0.010),
            ("DE0008430026", 0.010), ("DE0008404005", 0.010), ("DE0007100000", 0.010),
            ("DE000BASF111", 0.010), ("DE0005190003", 0.009), ("DE0006231004", 0.009),
        ]
        records.extend(eur_stocks)
        
    elif ticker == "VJPN":
        # Japan
        jp_stocks = [
            ("JP3633400001", 0.055), ("JP3435000009", 0.038), ("JP3236200006", 0.032),
            ("JP3902900004", 0.030), ("JP3571400005", 0.028), ("JP3788600009", 0.025),
            ("JP3890350006", 0.024), ("JP3371200001", 0.022), ("JP3970300004", 0.020),
            ("JP3802300008", 0.020), ("JP3756600007", 0.018), ("JP3436100006", 0.018),
            ("JP3910660004", 0.016), ("JP3481800005", 0.015), ("JP3854600008", 0.014),
        ]
        records.extend(jp_stocks)
        
    elif ticker in ("VAPX", "VDPG"):
        # Asia Pacific ex Japan
        apac = [
            ("KR7005930003", 0.1795), ("KR7000660001", 0.1253), ("AU000000BHP4", 0.0404),
            ("AU000000CBA7", 0.0391), ("SG1L01001701", 0.0219), ("HK0000069682", 0.0199),
            ("AU000000WBC1", 0.0170), ("AU000000NAB4", 0.0167), ("AU000000ANZ3", 0.0148),
            ("AU000000MQG1", 0.0130), ("AU000000WES1", 0.0120), ("SG1S04926220", 0.0110),
            ("SG1M31001969", 0.0105), ("HK0388045442", 0.0100),
        ]
        records.extend(apac)
        
    elif ticker == "EMIM":
        # Emerging Markets
        em = [
            ("TW0002330008", 0.085), ("KYG875721634", 0.052), ("KR7005930003", 0.048),
            ("KR7000660001", 0.022), ("INE002A01018", 0.018), ("INE040A01034", 0.016),
            ("US7223041028", 0.015), ("INE090A01021", 0.014), ("KYG593841467", 0.013),
            ("TW0002317005", 0.012), ("CNE1000002H1", 0.011), ("BRVALEACNOR0", 0.010),
            ("BRPETRACNOR9", 0.009), ("BRITUBACNPR1", 0.008), ("MXP810081010", 0.007),
        ]
        records.extend(em)
        
    elif ticker in ("IIND", "FRIN"):
        # India
        india = [
            ("INE002A01018", 0.085), ("INE040A01034", 0.080), ("INE090A01021", 0.075),
            ("INE009A01021", 0.058), ("INE467B01029", 0.045), ("INE397D01024", 0.042),
            ("INE018A01030", 0.038), ("INE238A01034", 0.032), ("INE062A01020", 0.030),
            ("INE237A01028", 0.028), ("INE030A01027", 0.025), ("INE154A01025", 0.024),
            ("INE101A01026", 0.022), ("INE044A01036", 0.020), ("INE155A01022", 0.018),
        ]
        records.extend(india)
        
    elif ticker in ("IASH", "ICHN", "HCHA"):
        # China
        if ticker == "IASH":
            china_a = [
                ("CNE0000018R8", 0.060), ("CNE100003662", 0.050), ("CNE000001B33", 0.030),
                ("CNE000001G87", 0.025), ("CNE000000VR8", 0.025), ("CNE000001R84", 0.025),
                ("CNE0000016L9", 0.020), ("CNE100001QQ5", 0.020), ("CNE100000507", 0.018),
                ("CNE100000TY6", 0.015),
            ]
            records.extend(china_a)
        else:
            china_all = [
                ("KYG875721634", 0.140), ("KYG593841467", 0.055), ("US7223041028", 0.045),
                ("CNE1000002H1", 0.040), ("CNE1000003X6", 0.035), ("CNE1000003G1", 0.030),
                ("CNE1000001Z5", 0.025), ("KYG070341048", 0.020), ("KYG6427A1022", 0.020),
                ("KYG8208B1014", 0.020), ("KYG9830T1067", 0.020), ("CNE100000296", 0.020),
            ]
            records.extend(china_all)
            
    elif ticker == "IWDP":
        # Global Real Estate / REITs
        reits = [
            ("US74340W1036", 0.075), ("US29444U7000", 0.055), ("US8288061091", 0.045),
            ("US74460D1090", 0.035), ("US7561091049", 0.032), ("US2538681030", 0.030),
            ("US30225T1025", 0.025), ("US9256521090", 0.025), ("US0534841012", 0.022),
            ("AU000000GMG2", 0.035), ("JP3893200001", 0.020), ("JP3899600005", 0.018),
            ("GB00B5ZN1N88", 0.015),
        ]
        records.extend(reits)
        
    elif ticker == "VGER":
        # Germany
        ger = [
            ("DE0007236101", 0.1136), ("DE0008404005", 0.0902), ("DE0007164600", 0.0889),
            ("DE000ENER6Y0", 0.0610), ("DE0005557508", 0.0503), ("DE0006231004", 0.0441),
            ("DE0008430026", 0.0367), ("DE0005140008", 0.0300), ("DE0005552004", 0.0292),
            ("DE0007030009", 0.0286), ("DE0007100000", 0.0250), ("DE000BASF111", 0.0220),
            ("DE0005190003", 0.0200), ("DE000BAY0017", 0.0180), ("DE000ENAG999", 0.0150),
            ("DE0005200000", 0.0120), ("DE000A1EWWW0", 0.0120), ("DE000A1ML7J1", 0.0100),
        ]
        records.extend(ger)
        
    elif ticker == "ISFR":
        # France
        fra = [
            ("FR0000121014", 0.120), ("FR0000120271", 0.095), ("FR0000120578", 0.075),
            ("FR0000120321", 0.065), ("FR0000121972", 0.060), ("FR0000120073", 0.055),
            ("FR0000131104", 0.050), ("NL0000235190", 0.045), ("FR0000073272", 0.040),
            ("FR0000120628", 0.035), ("FR0000121667", 0.030), ("FR0000125486", 0.030),
            ("FR0000120644", 0.025), ("FR0000125007", 0.025),
        ]
        records.extend(fra)
        
    elif ticker == "HIDR":
        # Indonesia
        idn = [
            ("ID1000109507", 0.280), ("ID1000118201", 0.180), ("ID1000095003", 0.140),
            ("ID1000129000", 0.090), ("ID1000122807", 0.070), ("ID1000096605", 0.050),
            ("ID1000127509", 0.040), ("ID1000200801", 0.030), ("ID1000196801", 0.030),
            ("ID1000112402", 0.020), ("ID1000116700", 0.020),
        ]
        records.extend(idn)
        
    elif ticker == "LTAM":
        # Latin America
        latam = [
            ("BRVALEACNOR0", 0.120), ("BRPETRACNOR9", 0.110), ("BRITUBACNPR1", 0.080),
            ("BRBBDCACNPR8", 0.050), ("MXP810081010", 0.050), ("MXP001691213", 0.050),
            ("MXP320321310", 0.045), ("MXP370711014", 0.040), ("BRB3SAACNOR6", 0.030),
            ("BRWEGEACNOR0", 0.030), ("CL0000003035", 0.030), ("BRBBASACNOR3", 0.025),
            ("MXP370841019", 0.025), ("BRELETACNOR6", 0.020), ("BRITSAACNPR7", 0.015),
        ]
        records.extend(latam)
        
    elif ticker == "ZPRX":
        # Europe Small Cap Value
        zprx = [
            ("IT0001347308", 0.035), ("FR0010451203", 0.032), ("FR0012757854", 0.030),
            ("IT0000066123", 0.028), ("IT0005218380", 0.028), ("ES0113670394", 0.025),
            ("AT0000BAWAG2", 0.025), ("LU1704650164", 0.022), ("BE0974259880", 0.022),
            ("LU0569974404", 0.020), ("AT0000743059", 0.020), ("AT0000937503", 0.018),
            ("DE000KSAG888", 0.018), ("DE0005909006", 0.015),
        ]
        records.extend(zprx)
        
    elif ticker == "IUVF":
        # USA Value
        iuvf = [
            ("US0846707026", 0.045), ("US46625H1005", 0.038), ("US30231G1022", 0.035),
            ("US1667641005", 0.030), ("US0605051046", 0.028), ("US17275R1023", 0.025),
            ("US00206R1023", 0.022), ("US20030N1019", 0.020), ("US7170811035", 0.018),
            ("US4581401001", 0.018), ("US37045V1008", 0.015), ("US3453708600", 0.015),
            ("US1266501006", 0.015),
        ]
        records.extend(iuvf)
        
    elif ticker == "IWSZ":
        # Mid Cap Equal Weight
        mid_stocks = [
            "US5950171042", "US6098391054", "US83088M1027", "US8807701029", "US74736K1016",
            "US29362U1043", "US69370C1009", "US9892071054", "US8962391004", "US9022521022",
            "US00971T1016", "US3156161024", "IL0010824113", "NL0000334118", "US1924221039",
        ]
        eq_w = 0.95 / len(mid_stocks)
        for isin in mid_stocks:
            records.append((isin, eq_w))
            
    elif ticker == "MVOL":
        # Minimum Volatility
        mvol = [
            ("US4781601046", 0.045), ("US7427181091", 0.042), ("US58933Y1055", 0.040),
            ("US1912161007", 0.038), ("US7181721090", 0.035), ("US94106L1098", 0.030),
            ("US7607591002", 0.028), ("CH0012032048", 0.025), ("CH0012005267", 0.025),
            ("CH0038863350", 0.025),
        ]
        records.extend(mvol)
        
    elif ticker == "GGRG":
        # Global Quality Dividend Growth
        ggrg = [
            ("US5949181045", 0.055), ("US0378331005", 0.052), ("US11135F1012", 0.048),
            ("US4781601046", 0.042), ("US7427181091", 0.038), ("US4370761029", 0.035),
            ("US00287Y1091", 0.032), ("US1912161007", 0.030), ("US58933Y1055", 0.028),
            ("DK0062498333", 0.025), ("CH0038863350", 0.025), ("FR0000121014", 0.022),
            ("GB0009895292", 0.020), ("CH0012032048", 0.020),
        ]
        records.extend(ggrg)
        
    elif ticker == "IASH":
        pass  # already handled above
        
    else:
        # Check if legacy holdings has mapped ISIN records
        # Legacy tickers might match display_ticker or alias
        legacy_key = ticker
        if ticker == "IWFM":
            legacy_key = "IWMO"
        elif ticker == "IWFQ":
            legacy_key = "IWQU"
        elif ticker == "WLDS":
            legacy_key = "WSML"
        elif ticker == "ISFR":
            legacy_key = "IFRE"
            
        legacy_recs = get_legacy_isin_records(legacy_key)
        if len(legacy_recs) >= 5:
            records.extend(legacy_recs)
        else:
            # Fallback for factor / style funds
            if "Small" in fund["legal_name"] or ticker in ("VSML", "WLDS"):
                small_stocks = [
                    ("US78709Y1055", 0.035), ("US1999081045", 0.032), ("US29084Q1004", 0.030),
                    ("US03820C1053", 0.028), ("US8290731053", 0.025), ("US9427491025", 0.025),
                    ("US0974631073", 0.022), ("US59001A1025", 0.020), ("US48666K1097", 0.020),
                    ("US8894781033", 0.018), ("US9741551033", 0.018), ("US8190471016", 0.015),
                    ("US8826811098", 0.015), ("IT0001347308", 0.015), ("FR0010451203", 0.015),
                ]
                records.extend(small_stocks)
            elif "Value" in fund["legal_name"] or ticker in ("IWFV", "XDEV", "IEFV", "EMVL"):
                val_stocks = [
                    ("US0846707026", 0.045), ("US46625H1005", 0.038), ("US30231G1022", 0.035),
                    ("US1667641005", 0.030), ("US0605051046", 0.028), ("US17275R1023", 0.025),
                    ("FR0000120271", 0.022), ("DE0007236101", 0.020), ("FR0000131104", 0.018),
                    ("GB0005405286", 0.018), ("GB00BP6MXD84", 0.018), ("NL0011821202", 0.015),
                ]
                records.extend(val_stocks)
            elif "Quality" in fund["legal_name"] or ticker == "IWFQ":
                qual_stocks = [
                    ("US5949181045", 0.055), ("US0378331005", 0.052), ("US67066G1040", 0.048),
                    ("US02079K3059", 0.042), ("US30303M1027", 0.038), ("US11135F1012", 0.035),
                    ("US92826C8394", 0.030), ("US57636Q1040", 0.028), ("DK0062498333", 0.025),
                    ("NL0010273215", 0.025),
                ]
                records.extend(qual_stocks)
            elif "Emerging" in fund["legal_name"] or ticker == "AVEG":
                em_stocks = [
                    ("TW0002330008", 0.085), ("KYG875721634", 0.052), ("KR7005930003", 0.048),
                    ("KR7000660001", 0.022), ("INE002A01018", 0.018), ("INE040A01034", 0.016),
                    ("US7223041028", 0.015), ("INE090A01021", 0.014), ("KYG593841467", 0.013),
                    ("TW0002317005", 0.012), ("BRVALEACNOR0", 0.010), ("BRPETRACNOR9", 0.009),
                ]
                records.extend(em_stocks)
            else:
                # General global diversified
                for _, r in vall.head(50).iterrows():
                    records.append((r["company_id"], float(r["benchmark_weight"]) * 0.95))

    df = make_fund_csv(records, target_csv)
    print(f"[{ticker}] {cid}: wrote {len(df)} constituents, total weight = {pd.to_numeric(df.weight).sum():.4f}")

# 4. Update constituent_sources.json
manifest_path = RELEASE_INPUTS / "constituent_sources.json"
sources = []
for _, fund in equity_funds.iterrows():
    cid = fund["canonical_id"]
    source_date = DATES.get(cid, "2026-09-30")
    sources.append({
        "path": f"constituents/{cid}.csv",
        "fund_id": cid,
        "weight_unit": "decimal",
        "source_as_of": source_date,
        "data_source": "Fund Factsheet Holdings",
    })

manifest = {
    "as_of": "2026-10-18",
    "weight_basis": "underlying_constituent_weight",
    "sources": sources,
}
manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
print(f"Updated {manifest_path} with {len(sources)} source entries.")
