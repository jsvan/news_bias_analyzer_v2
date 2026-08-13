"""
Entity resolution — layered, cheap-first (docs/ROADMAP_IDEAS_2026.md §12).

Layer 0: known-entity shortlist injected into the extraction prompt so the LLM
         reuses canonical names (stops variant drift at the source).
Layer 1: deterministic post-hoc normalization (honorifics, punctuation, alias
         table) to propose canonical_id merges — Entity.canonical_id already
         exists in the schema; merges are pointer-based and reversible.

Pure functions, stdlib only, except run_merge_job() which wires Layer 1 to the DB
(scheduled weekly — see scheduler/job_scheduler.py). Self-test:

    python -m analyzer.entity_resolution
"""

import re
import unicodedata
from difflib import SequenceMatcher

# Honorifics/titles stripped from person names. Longest-match-first.
_TITLES = [
    "president-elect", "vice president", "prime minister", "chancellor",
    "president", "chairman", "chairwoman", "secretary general", "secretary",
    "senator", "governor", "minister", "ambassador", "general", "colonel",
    "king", "queen", "prince", "princess", "sheikh", "ayatollah", "pope",
    "sir", "dame", "dr", "mr", "mrs", "ms",
]
_TITLE_RE = re.compile(
    r"^(?:(?:" + "|".join(re.escape(t) for t in sorted(_TITLES, key=len, reverse=True))
    + r")\.?\s+)+", re.IGNORECASE)

# LLM category-label prefixes ("People: Xi Jinping", "Country: China") — a
# closed list, NOT a generic strip-before-colon (that would mangle real titles
# like "Star Trek: Picard").
_CATEGORY_PREFIX_RE = re.compile(
    r"^(?:people|person|persons|country|countries|organization|organisation|org|"
    r"entity|entities|location|company)\s*:\s+", re.IGNORECASE)

# Trailing abbreviation parenthetical: "Bharatiya Janata Party (BJP)",
# "Islamic Revolutionary Guard Corps (IRGC)". Only a single unspaced token with
# >=2 uppercase letters qualifies — "(Japan)", "(Maoist)", "(Nawaz)" and the
# faction marker "(N)" are meaningful qualifiers and must survive.
_ABBR_PAREN_RE = re.compile(r"\s*\(([^()\s]{2,12})\)$")
# All-caps faction markers that are NOT abbreviations of the preceding name —
# stripping "(UBT)" would merge Shiv Sena's two rival factions into one party.
_PAREN_KEEP = frozenset({"ubt", "sp"})

# Corporate suffixes, org-type names only. "Strong" forms are unambiguous and
# always stripped; "weak" forms (Corp/Co/S.A.) strip only after a comma or when
# at least two tokens remain, so "News Corp" survives as the company's name.
_STRONG_SUFFIX = r"(?:inc|incorporated|ltd|limited|llc|corporation|plc|gmbh|ag|sa|s\.a)"
_WEAK_SUFFIX = r"(?:corp|co)"
_SUFFIX_RE = re.compile(
    r"(?P<sep>,\s*|\s+)(?P<suffix>" + _STRONG_SUFFIX + r"|" + _WEAK_SUFFIX + r")\.?$",
    re.IGNORECASE)
_WEAK_SUFFIX_RE = re.compile(r"^" + _WEAK_SUFFIX + r"$", re.IGNORECASE)
_ORG_TYPES = frozenset({"organization", "organisation", "business", "company", "political_party"})
# Company names whose suffix-stripped form collides with an unrelated entity
# ("Mars" the planet); listed here in full to stay distinct.
_SUFFIX_KEEP = frozenset({"mars, incorporated", "mars inc"})

# Hand-curated aliases: variant (normalized, lowercased) -> canonical display
# name. Curated 2026-08 by reviewing every tracked entity with >1 mention and
# all fuzzy merge candidates against the live corpus; each entry is a variant
# of the SAME real-world entity, not a lookalike ("Donald Trump Jr",
# "Mojtaba Khamenei", "DeepState", "Michael B. Jordan" are deliberately
# absent). Keys must be in post-normalization form: category prefixes,
# abbreviation parens, and corporate suffixes are already stripped by the time
# the alias lookup runs, so "bharatiya janata party (bjp)" is never a key.
ALIASES = {
    # --- countries / polities ---
    "us": "United States",
    "usa": "United States",
    "u.s.": "United States",
    "u.s": "United States",   # trailing-dot form after punctuation strip
    "u.s.a": "United States",
    "america": "United States",
    "united states of america": "United States",
    "the united states": "United States",
    "the united states of america": "United States",
    "uk": "United Kingdom",
    "u.k": "United Kingdom",
    "britain": "United Kingdom",
    "great britain": "United Kingdom",
    "the united kingdom": "United Kingdom",
    "eu": "European Union",
    "the european union": "European Union",
    "un": "United Nations",
    "the united nations": "United Nations",
    "prc": "China",
    "people's republic of china": "China",
    "russian federation": "Russia",
    "rusia": "Russia",                    # Spanish-language articles
    "republic of china": "Taiwan",
    "republic of korea": "South Korea",
    "democratic people's republic of korea": "North Korea",
    "dprk": "North Korea",
    "türkiye": "Turkey",
    "turkiye": "Turkey",
    "uae": "United Arab Emirates",
    "czechia": "Czech Republic",
    "ivory coast": "Côte d'Ivoire",
    "democratic republic of congo": "Democratic Republic of the Congo",
    "drc": "Democratic Republic of the Congo",
    "the netherlands": "Netherlands",
    "sout africa": "South Africa",        # scraped typo with real mentions
    "jordania": "Jordan",
    "finlandia": "Finland",
    "washington d.c": "Washington, D.C",
    # --- international organizations ---
    "who": "World Health Organization",
    "nato": "NATO",
    "north atlantic treaty organization": "NATO",
    "imf": "International Monetary Fund",
    "wto": "World Trade Organization",
    "world trade organisation": "World Trade Organization",
    "oecd": "OECD",
    "organisation for economic co-operation and development": "OECD",
    "organization for economic cooperation and development": "OECD",
    "opec": "OPEC",
    "organization of the petroleum exporting countries": "OPEC",
    "iaea": "International Atomic Energy Agency",
    "international maritime organisation": "International Maritime Organization",
    "shanghai cooperation organisation": "Shanghai Cooperation Organization",
    "un office for the coordination of humanitarian affairs":
        "United Nations Office for the Coordination of Humanitarian Affairs",
    "un working group on arbitrary detention":
        "United Nations Working Group on Arbitrary Detention",
    "uefa": "UEFA",
    "union of european football associations": "UEFA",
    # --- militaries / armed groups ---
    "irgc": "Islamic Revolutionary Guard Corps",
    "iranian islamic revolutionary guard corps": "Islamic Revolutionary Guard Corps",
    "iranian revolutionary guard corps": "Islamic Revolutionary Guard Corps",
    "iranian revolutionary guard": "Islamic Revolutionary Guard Corps",
    "iranian revolutionary guards": "Islamic Revolutionary Guard Corps",
    "iran's islamic revolutionary guard corps": "Islamic Revolutionary Guard Corps",
    "idf": "Israel Defense Forces",
    "the israel defense forces": "Israel Defense Forces",
    "israeli defense forces": "Israel Defense Forces",
    "houthi": "Houthis",
    "houthi movement": "Houthis",
    "yemen houthis": "Houthis",
    "yemeni houthis": "Houthis",
    "isis": "Islamic State",
    "isil": "Islamic State",
    "daesh": "Islamic State",
    "islamic state khurasan province": "Islamic State – Khorasan Province",
    "al shabaab": "Al-Shabaab",
    "kataeb hezbollah": "Kataib Hezbollah",
    "tehreek-i-taliban pakistan": "Tehreek-e-Taliban Pakistan",
    "tehrik-e-taliban pakistan": "Tehreek-e-Taliban Pakistan",
    "jama'at nasr al-islam wal muslimin": "Jama'at Nusrat al-Islam wal-Muslimin",
    "jama'at nusrat al islam wal muslimeen": "Jama'at Nusrat al-Islam wal-Muslimin",
    "jama'at nusrat al-islam wal muslimin": "Jama'at Nusrat al-Islam wal-Muslimin",
    "fitna al hindustan": "Fitna-al-Hindustan",
    "fitna-al hindustan": "Fitna-al-Hindustan",
    "popular mobilisation forces": "Popular Mobilization Forces",
    "popular mobil mobilisation forces": "Popular Mobilization Forces",
    "ukraine's armed forces": "Ukrainian Armed Forces",
    "ukrainian air forces": "Ukrainian Air Force",
    "the pentagon": "Pentagon",
    "the kremlin": "Kremlin",
    "submarine rotation force west": "Submarine Rotational Force-West",
    # --- state agencies / ministries ---
    "fbi": "Federal Bureau of Investigation",
    "cia": "Central Intelligence Agency",
    "cdc": "Centers for Disease Control and Prevention",
    "africa centers for disease control and prevention":
        "Africa Centres for Disease Control and Prevention",
    "dhs": "Department of Homeland Security",
    "fda": "Food and Drug Administration",
    "nasa": "NASA",
    "national aeronautics and space administration": "NASA",
    "nhs": "National Health Service",
    "federal reserve system": "Federal Reserve",
    "russian defense ministry": "Ministry of Defence of the Russian Federation",
    "russian defence ministry": "Ministry of Defence of the Russian Federation",
    "federal security service": "Federal Security Service of the Russian Federation",
    "fsb": "Federal Security Service of the Russian Federation",
    "chinese foreign ministry": "Ministry of Foreign Affairs of the People's Republic of China",
    "ministry of interior": "Ministry of the Interior",
    "ministry of interior and safety": "Ministry of the Interior and Safety",
    "supreme national security council of iran": "Supreme National Security Council",
    "india meteorological department": "India Meteorological Department",
    "indian meteorological department": "India Meteorological Department",
    "indian metrological department": "India Meteorological Department",
    "korean central news agency": "Korean Central News Agency",
    "new york police department": "New York City Police Department",
    "nypd": "New York City Police Department",
    "new york fire department": "New York City Fire Department",
    "guarda nacional": "Guardia Nacional",
    "foreign, commonwealth and development office": "Foreign, Commonwealth & Development Office",
    "centers for medicare & medicaid services": "Centers for Medicare and Medicaid Services",
    "the met office": "Met Office",
    "the supreme court of the united states": "Supreme Court of the United States",
    "united states federal government": "United States Government",
    "united states (government)": "United States Government",
    "indian government": "Government of India",
    "india (government)": "Government of India",
    "indonesia's government": "Indonesian government",
    "ukraine (government)": "Ukrainian government",
    "kerala state government": "Kerala government",
    "the trump administration": "Trump administration",
    "zaporozhye nuclear power plant": "Zaporizhzhia Nuclear Power Plant",
    "lugansk people's republic": "Luhansk People's Republic",
    # --- parties / movements ---
    "bjp": "Bharatiya Janata Party",
    "bharatiya janta party": "Bharatiya Janata Party",
    "cockroach janata party": "Cockroach Janta party",
    "afd": "Alternative for Germany",
    "alternative für deutschland": "Alternative for Germany",
    "cdu": "Christian Democratic Union of Germany",
    "christian democratic union": "Christian Democratic Union of Germany",
    "csu": "Christian Social Union in Bavaria",
    "spd": "Social Democratic Party of Germany",
    "maga": "Make America Great Again",
    "mag a": "Make America Great Again",
    "gop": "Republican Party",
    "republicans": "Republican Party",
    "democrats": "Democratic Party",
    "the democratic party": "Democratic Party",
    "labour": "Labour Party",
    "liberal democratic party of japan": "Liberal Democratic Party",
    "liberal democratic party (japan)": "Liberal Democratic Party",
    "freedom party (austria)": "Freedom Party of Austria",
    "pakistan people's party": "Pakistan Peoples Party",
    "pakistan muslim league (nawaz)": "Pakistan Muslim League-Nawaz",
    "bangladesh national party": "Bangladesh Nationalist Party",
    "australian labour party": "Australian Labor Party",
    "indian national development inclusive alliance":
        "Indian National Developmental Inclusive Alliance",
    "the green party": "Green Party",
    "the muslim brotherhood": "Muslim Brotherhood",
    "woman, life, freedom": "Women, Life, Freedom",
    "jammu and kashmir joint awami action committee": "Joint Awami Action Committee",
    "jammu kashmir joint awami action committee": "Joint Awami Action Committee",
    # --- media ---
    "bbc": "BBC",
    "british broadcasting corporation": "BBC",
    "new york times": "The New York Times",
    "washington post": "The Washington Post",
    "wall street journal": "The Wall Street Journal",
    "the new york post": "New York Post",
    "the associated press": "Associated Press",
    "new yorker": "The New Yorker",
    "times of india": "The Times of India",
    "bfm tv": "BFMTV",
    "the white house": "White House",
    # --- companies / products ---
    "meta platforms": "Meta",
    "amazon.com": "Amazon",
    "twitter": "X",
    "x corp": "X",
    "samsung": "Samsung Electronics",
    "exxon mobil": "ExxonMobil",
    "exxon mobil corporation": "ExxonMobil",
    "exxonmobil corporation": "ExxonMobil",
    "jp morgan": "JPMorgan",
    "coca cola": "Coca-Cola",
    "ariane group": "ArianeGroup",
    "banc sabadell": "Banco Sabadell",
    "commerzbank ag": "Commerzbank",
    "volkswagen ag": "Volkswagen",
    "rheinmetall ag": "Rheinmetall",
    "hapag-lloyd ag": "Hapag-Lloyd",
    "deutsche bahn ag": "Deutsche Bahn",
    "deutsche bank ag": "Deutsche Bank",
    "mcdonald s": "McDonald's",
    "trump media": "Trump Media & Technology Group",
    "trump media & technology": "Trump Media & Technology Group",
    "trump media and technology group": "Trump Media & Technology Group",
    "the trump organization": "Trump Organization",
    "warner bros discovery": "Warner Bros. Discovery",
    "1800 respect": "1800RESPECT",
    "humansfirst": "Humans First",
    "inter miami cf": "Inter Miami",
    "olympiacos fc": "Olympiacos",
    "al hilal": "Al-Hilal",
    "al nassr": "Al-Nassr",
    "atlético de madrid": "Atlético Madrid",
    "argentina football association": "Argentine Football Association",
    "asia football confederation": "Asian Football Confederation",
    "korean football association": "Korea Football Association",
    "mexican national football team": "Mexico national football team",
    "japan's imperial family": "Japanese Imperial Family",
    "no 10 north": "No. 10 North",
    # --- people: heads of state and government ---
    "trump": "Donald Trump",
    "donald j. trump": "Donald Trump",
    "donald j trump": "Donald Trump",
    "donald john trump": "Donald Trump",
    "joseph biden": "Joe Biden",
    "joseph r. biden jr": "Joe Biden",
    "joseph r biden jr": "Joe Biden",
    "joseph robinette biden jr": "Joe Biden",
    "barack hussein obama": "Barack Obama",
    "barack hussein obama ii": "Barack Obama",
    "kamala devi harris": "Kamala Harris",
    "vladimir vladimirovich putin": "Vladimir Putin",
    "volodymyr zelenskyy": "Volodymyr Zelensky",
    "volodymyr zelenskiy": "Volodymyr Zelensky",
    "volodymyr zelenskyi": "Volodymyr Zelensky",
    "vladimir zelensky": "Volodymyr Zelensky",
    "volodímir zelenski": "Volodymyr Zelensky",
    "volodimír zelenski": "Volodymyr Zelensky",
    "volodymyr oleksandrovych zelensky": "Volodymyr Zelensky",
    "volodymyr oleksandrovych zelenskyy": "Volodymyr Zelensky",
    "zelensky": "Volodymyr Zelensky",
    "zelenskyy": "Volodymyr Zelensky",
    "zelenski": "Volodymyr Zelensky",
    "ukrainian president volodymyr zelensky": "Volodymyr Zelensky",
    "ukrainian president volodymyr zelenskyy": "Volodymyr Zelensky",
    "benjamin netanjahu": "Benjamin Netanyahu",
    "recep tayyip erdogan": "Recep Tayyip Erdoğan",
    "viktor orban": "Viktor Orbán",
    "luiz inacio lula da silva": "Luiz Inácio Lula da Silva",
    "nicolás maduro moros": "Nicolás Maduro",
    "nicolas maduro": "Nicolás Maduro",
    "pedro sanchez": "Pedro Sánchez",
    "kim jong-un": "Kim Jong Un",
    "yoon suk-yeol": "Yoon Suk Yeol",
    "yoon suk-yol": "Yoon Suk Yeol",
    "lee jae myung": "Lee Jae-myung",
    "lee jae-myeung": "Lee Jae-myung",
    "kim keon-hee": "Kim Keon Hee",
    "sanae takai": "Sanae Takaichi",
    "shinjirō koizumi": "Shinjiro Koizumi",
    "bashar assad": "Bashar al-Assad",
    "ahmad al-sharaa": "Ahmed al-Sharaa",
    "ahmad al-sharah": "Ahmed al-Sharaa",
    "ahmed al shara": "Ahmed al-Sharaa",
    "abdel fattah al-sisi": "Abdel Fattah el-Sisi",
    "abdel-fattah el-sissi": "Abdel Fattah el-Sisi",
    "mohamed vi": "Mohammed VI",
    "mohamed vi of morocco": "Mohammed VI",
    "mohammed vi of morocco": "Mohammed VI",
    "mohammad bin salman": "Mohammed bin Salman",
    "khalifa hifter": "Khalifa Haftar",
    "abdul hamid dbeibeh": "Abdul Hamid Dbeibah",
    "abdul-hamed dbeibah": "Abdul Hamid Dbeibah",
    "mohammed hamdan daglo": "Mohamed Hamdan Dagalo",
    "yower kaguta museveni": "Yoweri Kaguta Museveni",
    "joseph nyuma boakai sr": "Joseph Nyuma Boakai",
    "masoud pezeshkian": "Masoud Pezeshkian",
    "massoud pezeshkian": "Masoud Pezeshkian",
    "claudia sheinbaum pardo": "Claudia Sheinbaum",
    "mette fredriksen": "Mette Frederiksen",
    "lars lokke rasmussen": "Lars Løkke Rasmussen",
    "jose luis rodriguez zapatero": "José Luis Rodríguez Zapatero",
    "jose antonio kast": "José Antonio Kast",
    "karlo nawrocki": "Karol Nawrocki",
    "tamas sulyok": "Tamás Sulyok",
    "tufan erhurman": "Tufan Erhürman",
    "franklin delano roosevelt": "Franklin D. Roosevelt",
    "margaret hilda thatcher": "Margaret Thatcher",
    "fidel castro ruz": "Fidel Castro",
    "nicholas ii of russia": "Nicholas II of Russia",
    # --- people: politicians and officials ---
    "lindsey o. graham": "Lindsey Graham",
    "randal howard paul": "Rand Paul",
    "randall howard paul": "Rand Paul",
    "addison mitchell mcconnell": "Mitch McConnell",
    "addison mitchell mcconnell iii": "Mitch McConnell",
    "charles ellis schumer": "Chuck Schumer",
    "charles e. schumer": "Chuck Schumer",
    "edward j. markey": "Ed Markey",
    "edward john markey": "Ed Markey",
    "jd vance": "JD Vance",
    "j. d. vance": "JD Vance",
    "j.d. vance": "JD Vance",
    "james daniel vance": "JD Vance",
    "james david vance": "JD Vance",
    "robert f kennedy jr": "Robert F. Kennedy Jr",
    "robert f. kennedy, jr": "Robert F. Kennedy Jr",
    "robert francis kennedy jr": "Robert F. Kennedy Jr",
    "rfk jr": "Robert F. Kennedy Jr",
    "peter hegseth": "Pete Hegseth",
    "peter b. hegseth": "Pete Hegseth",
    "peter s. hegseth": "Pete Hegseth",
    "peter j. hegseth": "Pete Hegseth",
    "peter p. hegseth": "Pete Hegseth",
    "anthony stephen fauci": "Anthony Fauci",
    "anthony s. fauci": "Anthony Fauci",
    "stephen k. bannon": "Steve Bannon",
    "stephen kevin bannon": "Steve Bannon",
    "kevin h. warsh": "Kevin Warsh",
    "kevin m. warsh": "Kevin Warsh",
    "jerome h. powell": "Jerome Powell",
    "lisa d. cook": "Lisa Cook",
    "lisa m. cook": "Lisa Cook",
    "neil m. gorsuch": "Neil Gorsuch",
    "michael a. waltz": "Michael Waltz",
    "muriel e. bowser": "Muriel Bowser",
    "mehmet c. oz": "Mehmet Oz",
    "j. b. pritzker": "J.B. Pritzker",
    "nicholas g. garaufis": "Nicholas Garaufis",
    "bennie g. thompson": "Bennie Thompson",
    "dan j. sullivan": "Dan Sullivan",
    "raul labrador": "Raúl Labrador",
    "julian castro": "Julián Castro",
    "josh kushner": "Joshua Kushner",
    "robert a. iger": "Robert Iger",
    # --- people: international figures ---
    "antonio guterres": "António Guterres",
    "qasem soleimani": "Qassem Soleimani",
    "ali jamenei": "Ali Khamenei",
    "sayyid ali hosseini khamenei": "Ali Khamenei",
    "mohsen rezaee": "Mohsen Rezaei",
    "abbas araqchi": "Abbas Araghchi",
    "esmaeil baqaei": "Esmail Baghaei",
    "hossein taeeb": "Hossein Taeb",
    "mohammad baqer qalibaf": "Mohammad Bagher Ghalibaf",
    "mohammad baqer zolqadr": "Mohammad Bagher Zolghadr",
    "abdolnaser hemmati": "Abdolnasser Hemmati",
    "ahmad wahidi": "Ahmad Vahidi",
    "sergei lavrov": "Sergey Lavrov",
    "serguéi lavrov": "Sergey Lavrov",
    "sergey shoigu": "Sergei Shoigu",
    "dmitri medvedev": "Dmitry Medvedev",
    "boris nadejdine": "Boris Nadezhdin",
    "kiril dmítriev": "Kirill Dmitriev",
    "sergey sobyanin": "Sergei Sobyanin",
    "sergey kiriyenko": "Sergei Kiriyenko",
    "andrei vorobyov": "Andrey Vorobyov",
    "alexéi navalni": "Alexei Navalny",
    "oleksandr sirski": "Oleksandr Syrskyi",
    "oleksandr syrski": "Oleksandr Syrskyi",
    "oleksandr syrsky": "Oleksandr Syrskyi",
    "myhailo fedorov": "Mykhailo Fedorov",
    "mykhaïlo fedorov": "Mykhailo Fedorov",
    "dmytro lubynets": "Dmytro Lubinets",
    "yuliia svyrydenko": "Yulia Svyrydenko",
    "sergii koretskyi": "Serhii Koretskyi",
    "serhiy koretskyi": "Serhii Koretskyi",
    "serhiy korestskyi": "Serhii Koretskyi",
    "yevhenii khmara": "Yevhen Khmara",
    "volker turk": "Volker Türk",
    "jean-luc melenchon": "Jean-Luc Mélenchon",
    "jaroslaw kaczynski": "Jarosław Kaczyński",
    "kriszstof bosak": "Krzysztof Bosak",
    "ekrem imamoglu": "Ekrem İmamoğlu",
    "abdullah ocalan": "Abdullah Öcalan",
    "itamar ben gvir": "Itamar Ben-Gvir",
    "gadi eizenkot": "Gadi Eisenkot",
    "maria corina machado": "María Corina Machado",
    "delcy rodriguez": "Delcy Rodríguez",
    "jorge rodriguez": "Jorge Rodríguez",
    "gilbert f. houngbo": "Gilbert Houngbo",
    "turki al sheikh": "Turki Alalshikh",
    "talal chaudhry": "Talal Chaudhry",
    "tallal chaudhry": "Talal Chaudhry",
    "muhamad hariyadi": "Muhammad Hariyadi",
    "balvinder singh chhabra": "Balwinder Singh Chhabra",
    "gitanjali j angmo": "Gitanjali J. Angmo",
    "robinder nath sachdev": "Robinder Sachdev",
    "d. k. shivakumar": "D.K. Shivakumar",
    "v. d. satheesan": "V.D. Satheesan",
    "fernando grande-marlaska gómez": "Fernando Grande-Marlaska",
    "josé manuel albares bueno": "José Manuel Albares",
    "jose manuel albares": "José Manuel Albares",
    "laurent nunez": "Laurent Nuñez",
    "laurent núñez": "Laurent Nuñez",
    "catherine pegard": "Catherine Pégard",
    "andras baka": "András Baka",
    "milan nedeljkovic": "Milan Nedeljković",
    # --- people: sport / culture ---
    "xavi hernandez": "Xavi Hernández",
    "tadej pogacar": "Tadej Pogačar",
    "kylian mbappe": "Kylian Mbappé",
    "jose mourinho": "José Mourinho",
    "cristiano ronaldo dos santos aveiro": "Cristiano Ronaldo",
    "aleksandar ceferin": "Aleksander Čeferin",
    "aleksander ceferin": "Aleksander Čeferin",
    "nasser al-khelaïfi": "Nasser Al-Khelaifi",
    "penelope cruz": "Penélope Cruz",
    "georgina rodriguez": "Georgina Rodríguez",
    "marketa irglova": "Markéta Irglová",
    "domingo german": "Domingo Germán",
    "luis manuel otero alcantara": "Luis Manuel Otero Alcántara",
    "pablo martin paez gavira": "Pablo Martín Páez Gavira",
    "folarín balogun": "Folarin Balogun",
    "desire doue": "Desiré Doué",
    "desire doué": "Desiré Doué",
    "rafa jódar": "Rafael Jódar",
    "rafael jodar": "Rafael Jódar",
    "francisco martin": "Francisco Martín",
    "suni williams": "Sunita Williams",
    "j. k. rowling": "J.K. Rowling",
    "frank‐walter steinmeier": "Frank-Walter Steinmeier",  # U+2010 hyphen variant
    # --- concepts with spelling variants ---
    "el nino": "El Niño",
    "marihuana": "Marijuana",
    "testosterona": "Testosterone",
    "heat wave": "Heatwave",
    "heat waves": "Heatwave",
    "heatwaves": "Heatwave",
    "ebolavirus": "Ebola virus",
    "academy award": "Academy Awards",
    "geneva convention": "Geneva Conventions",
    "world pride": "WorldPride",
    "copa america": "Copa América",
}


def _strip_corporate_suffix(s: str) -> str:
    """Peel trailing corporate suffixes ("Samsung Electronics Co., Ltd" ->
    "Samsung Electronics"). Weak suffixes (Corp/Co) need a comma separator or
    >=2 remaining tokens, so single-token names like "News Corp" are kept."""
    while True:
        m = _SUFFIX_RE.search(s)
        if not m:
            return s
        rest = s[:m.start()].rstrip(" ,.")
        if not rest:
            return s
        is_weak = bool(_WEAK_SUFFIX_RE.match(m.group("suffix")))
        has_comma = "," in m.group("sep")
        if is_weak and not has_comma and len(rest.split()) < 2:
            return s
        s = rest


def normalize_name(name: str, entity_type: str = "") -> str:
    """Canonical comparison form: unicode-normalized, title-stripped, tidied.

    Returns a display-cased canonical name (not lowercased) so it can be used
    directly as the merged entity's name.
    """
    s = unicodedata.normalize("NFKC", name).strip()
    # Curly quote/apostrophe variants split otherwise-identical names
    # ("Pakistan People's Party" vs "Pakistan People’s Party").
    s = s.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    s = re.sub(r"\s+", " ", s)
    s = s.strip(" \"'.,;:")
    s = _CATEGORY_PREFIX_RE.sub("", s)
    m = _ABBR_PAREN_RE.search(s)
    if (m and sum(1 for c in m.group(1) if c.isupper()) >= 2
            and m.group(1).lower() not in _PAREN_KEEP):
        s = s[:m.start()].rstrip()
    if entity_type in _ORG_TYPES and s.lower() not in _SUFFIX_KEEP:
        s = _strip_corporate_suffix(s)
    if entity_type in ("person", "political_leader", ""):
        s = _TITLE_RE.sub("", s)
    alias = ALIASES.get(s.lower())
    if alias:
        return alias
    return s


def merge_key(name: str, entity_type: str = "") -> str:
    """Case/space-insensitive key two entities must share to be merge candidates."""
    return normalize_name(name, entity_type).lower()


def propose_merges(entities, fuzzy_threshold: float = 0.85):
    """Propose canonical_id merges over [(id, name, entity_type, mention_count)].

    Exact merge-key collisions merge automatically toward the most-mentioned
    member; near-misses above fuzzy_threshold (SequenceMatcher on merge keys)
    are returned separately for review, never auto-merged.

    Returns (auto, review):
      auto:   [(loser_id, canonical_id, reason)]
      review: [(id_a, id_b, similarity)]
    """
    normalized = [(eid, merge_key(name, etype), count)
                  for eid, name, etype, count in entities]

    groups = {}
    for eid, key, count in normalized:
        groups.setdefault(key, []).append((eid, count))

    auto = []
    for key, members in groups.items():
        if len(members) < 2:
            continue
        members.sort(key=lambda t: -t[1])
        canonical = members[0][0]
        auto.extend((eid, canonical, f"exact:{key}") for eid, _ in members[1:])

    # Fuzzy pass over group representatives only (keeps it near-linear in practice).
    review = []
    reps = [(members[0][0], key) for key, members in groups.items()
            if (members.sort(key=lambda t: -t[1]) or True)]
    reps.sort(key=lambda t: t[1])
    for i, (id_a, key_a) in enumerate(reps):
        for id_b, key_b in reps[i + 1:]:
            # keys are sorted; stop when even the prefix diverges too far
            if key_b[:2] != key_a[:2]:
                break
            sim = SequenceMatcher(None, key_a, key_b).ratio()
            if sim >= fuzzy_threshold:
                review.append((id_a, id_b, round(sim, 3)))
    return auto, review


def run_merge_job(session, fuzzy_threshold: float = 0.85) -> int:
    """DB wiring for Layer 1: auto-merge canonical entities with colliding merge keys.

    Only the exact-match tier of propose_merges() is applied — the fuzzy "review" band is
    deliberately left alone (no human review queue exists; the conservative default is to
    leave near-misses as separate entities rather than risk a bad automatic merge).
    Non-destructive: sets canonical_id, never deletes or rewrites a row. Intended to run
    weekly via scheduler/job_scheduler.py.

    Returns the number of entities merged.
    """
    from sqlalchemy import text

    candidates = session.execute(text("""
        SELECT e.id, e.name, e.entity_type, COUNT(em.id) AS mention_count
        FROM entities e
        LEFT JOIN entity_mentions em ON em.entity_id = e.id
        WHERE e.canonical_id IS NULL
        GROUP BY e.id, e.name, e.entity_type
    """)).fetchall()

    entities = [(row.id, row.name, row.entity_type, row.mention_count) for row in candidates]
    auto, _review = propose_merges(entities, fuzzy_threshold=fuzzy_threshold)

    for loser_id, canonical_id, _reason in auto:
        session.execute(
            text("UPDATE entities SET canonical_id = :canonical_id WHERE id = :loser_id"),
            {"canonical_id": canonical_id, "loser_id": loser_id}
        )
    session.commit()
    return len(auto)


def known_entity_shortlist(article_text: str, known_entities, limit: int = 30):
    """Layer 0: canonical names of tracked entities that appear in this article.

    known_entities: [(canonical_name, mention_count)], assumed pre-sorted or not.
    Substring match on the normalized text — false positives are harmless (the
    LLM ignores names not actually in the article); false negatives just mean
    no hint. Most-mentioned entities win the `limit` cut.
    """
    text = unicodedata.normalize("NFKC", article_text).lower()
    hits = [(name, count) for name, count in known_entities
            if len(name) > 2 and name.lower() in text]
    hits.sort(key=lambda t: -t[1])
    return [name for name, _ in hits[:limit]]


def format_shortlist_block(names) -> str:
    """Prompt block appended to the article text when the shortlist is non-empty."""
    if not names:
        return ""
    return (
        "\n\nKNOWN ENTITIES: These entities are already tracked under these exact "
        "canonical names. If any of them appear in this article, report them using "
        "these names verbatim (do not use variants, titles, or translations):\n- "
        + "\n- ".join(names)
    )


def self_test():
    # normalization: titles, unicode, aliases
    assert normalize_name("President Joe Biden", "person") == "Joe Biden"
    assert normalize_name("prime minister  Narendra Modi", "political_leader") == "Narendra Modi"
    assert normalize_name("  “Emmanuel Macron”. ") == "Emmanuel Macron"
    assert normalize_name("US", "sovereign_state") == "United States"
    assert normalize_name("u.s.") == "United States"
    assert normalize_name("EU") == "European Union"
    # non-person types keep leading words that merely look like titles
    assert normalize_name("General Motors", "company") == "General Motors"

    # curated aliases: same-entity name variants collapse to one canonical name
    assert normalize_name("Donald J. Trump", "person") == "Donald Trump"
    assert normalize_name("Volodymyr Zelenskyy", "person") == "Volodymyr Zelensky"
    assert normalize_name("United States of America", "country") == "United States"
    # ...but lookalikes stay distinct
    assert normalize_name("Donald Trump Jr", "person") == "Donald Trump Jr"
    assert normalize_name("Mojtaba Khamenei", "person") == "Mojtaba Khamenei"

    # curly-quote unification
    assert normalize_name("Pakistan People’s Party", "organization") == \
        normalize_name("Pakistan People's Party", "organization")

    # category-label prefixes are stripped; real colon titles are not
    assert normalize_name("People: Xi Jinping", "person") == "Xi Jinping"
    assert normalize_name("Country: China", "country") == "China"
    assert normalize_name("Star Trek: Picard", "concept") == "Star Trek: Picard"

    # trailing abbreviation parentheticals go; meaningful qualifiers stay
    assert normalize_name("Bharatiya Janata Party (BJP)", "organization") == "Bharatiya Janata Party"
    assert normalize_name("Alternative for Germany (AfD)", "organization") == "Alternative for Germany"
    assert normalize_name("Liberal Democratic Party (Japan)", "organization") == "Liberal Democratic Party"
    assert normalize_name("Pakistan Muslim League (N)", "organization") == "Pakistan Muslim League (N)"
    assert normalize_name("Communist Party of India (Maoist)", "organization") == \
        "Communist Party of India (Maoist)"
    # faction markers that merely look like abbreviations stay put
    assert normalize_name("Shiv Sena (UBT)", "organization") == "Shiv Sena (UBT)"

    # corporate suffixes strip for org types; "News Corp" survives whole
    assert normalize_name("Samsung Electronics Co., Ltd", "business") == "Samsung Electronics"
    assert normalize_name("Tesla, Inc", "organization") == "Tesla"
    assert normalize_name("Nvidia Corporation", "organization") == "Nvidia"
    assert normalize_name("Deutsche Bahn AG", "organization") == "Deutsche Bahn"
    assert normalize_name("News Corp", "organization") == "News Corp"
    assert normalize_name("Google LLC", "business") == "Google"
    # ...and the candy company never collapses onto the planet
    assert normalize_name("Mars, Incorporated", "organization") == "Mars, Incorporated"

    # merges: exact collisions auto-merge toward most mentions; fuzzy goes to review
    entities = [
        (1, "Joe Biden", "person", 900),
        (2, "President Joe Biden", "person", 50),
        (3, "joe biden", "person", 5),
        (4, "Joseph Biden", "person", 10),      # alias table folds this in too
        (5, "Ursula von der Leyen", "person", 300),
        (6, "US", "sovereign_state", 400),
        (7, "United States", "sovereign_state", 5000),
        (8, "Donald Trump", "person", 500),
        (9, "Donald Trump Jr", "person", 20),   # different person: must NOT merge
    ]
    auto, review = propose_merges(entities)
    merged = {(loser, canon) for loser, canon, _ in auto}
    assert (2, 1) in merged and (3, 1) in merged and (4, 1) in merged, auto
    assert (6, 7) in merged, auto  # alias table folds US into United States
    assert all(loser != 5 for loser, _, _ in auto)
    assert all(9 not in (loser, canon) for loser, canon, _ in auto), auto

    # shortlist: present entities found, absent ones not, limit respects mentions
    text = "In Berlin, Chancellor Olaf Scholz met Emmanuel Macron to discuss the European Union."
    known = [("Emmanuel Macron", 500), ("Olaf Scholz", 400),
             ("European Union", 4000), ("Vladimir Putin", 9000)]
    hits = known_entity_shortlist(text, known, limit=2)
    assert hits == ["European Union", "Emmanuel Macron"], hits
    assert "Vladimir Putin" not in hits

    block = format_shortlist_block(hits)
    assert "canonical names" in block and "- Emmanuel Macron" in block
    assert format_shortlist_block([]) == ""

    print("entity_resolution self-test OK")


if __name__ == "__main__":
    self_test()
