import streamlit as st
from pulp import *
from itertools import combinations
from collections import Counter
from more_itertools import distinct_combinations
import pandas as pd
import io

st.set_page_config(page_title="Lautojen optimointi", layout="centered")
st.title("📏 Lautakasa")
# ------------------------
# SESSION STATE INIT
# ------------------------

if "tarpeet" not in st.session_state:
    st.session_state.tarpeet = [{"pituus": 2000, "maara": 2}]

if "laudat" not in st.session_state:
    st.session_state.laudat = [4200, 4800]

# ------------------------
# Tarpeet – dynaamiset kentät
# ------------------------

st.subheader("🔧 Tarpeet")
with st.container(border=True):
    remove_tarve = None
    for i, t in enumerate(st.session_state.tarpeet):
        col1, col2, col3 = st.columns([1, 1, 1])
        with col1:
            t["pituus"] = st.number_input(f"Pituus {i+1}", min_value=100, max_value=10000, value=t["pituus"], key=f"pituus_{i}")
        with col2:
            t["maara"] = st.number_input(f"Määrä {i+1}", min_value=1, max_value=100, value=t["maara"], key=f"maara_{i}")
        with col3:
            if st.button("🗑️", key=f"remove_tarve_{i}"):
                remove_tarve = i

    if remove_tarve is not None:
        st.session_state.tarpeet.pop(remove_tarve)
        st.rerun()

    if st.button("➕ Lisää tarve"):
        st.session_state.tarpeet.append({"pituus": 1000, "maara": 1})
        st.rerun()
        #st.session_state.tarpeet = st.session_state.tarpeet + [{"pituus": 1000, "maara": 1}]

# ------------------------
# Laudat – dynaamiset kentät
# ------------------------

st.subheader("🪵 Saatavilla olevat laudat")
with st.container(border=True):
    remove_lauta = None
    for i, l in enumerate(st.session_state.laudat):
        col1, col2 = st.columns([1, 1])
        with col1:
            st.session_state.laudat[i] = st.number_input(f"Lauta {i+1} pituus", min_value=100, max_value=10000, value=l, key=f"lauta_{i}")
        with col2:
            if st.button("🗑️", key=f"remove_lauta_{i}"):
                remove_lauta = i

    if remove_lauta is not None:
        st.session_state.laudat.pop(remove_lauta)
        st.rerun()

    if st.button("➕ Lisää lauta"):
        st.session_state.laudat.append(3000)
        st.rerun()

# ------------------------
# Muut asetukset
# ------------------------

st.subheader("⚙️ Asetukset")
with st.container(border=True):
    max_combo_len = st.slider("Maksimiyhdistelmän pituus (pätkien määrä laudalla)", 1, 10, 4)
    pakollinenhukkaprosentti = st.slider("Pakollinen minimihukka (%) per lauta (paitsi pätkä = lauta)", 0, 20, 0, ) / 100

# ------------------------
# Ratkaisu
# ------------------------
st.text("")
if st.button(" ✨ Laske "):
    try:
        tarpeet = [(t["pituus"], t["maara"]) for t in st.session_state.tarpeet]
        laudat = st.session_state.laudat

        patkat = []
        for p, m in tarpeet:
            patkat.extend([p] * m)

        combo_id = 0
        yhdistelmat = {}

        # Luodaan määrä-pohjainen Counter
        ptk_counter = Counter(patkat)

        # Muunnetaan se lista-muotoon, missä pätkä esiintyy vain kerran (uniq-pätkät)
        uniq_patkat = list(ptk_counter.keys())

        # Rakennetaan yhdistelmät
        for r in range(1, max_combo_len + 1):
            for combo in distinct_combinations(uniq_patkat, r):
                # Rakennetaan kaikki mahdolliset monistukset näistä r-pituisten yhdistelmien pätkistä
                def generate_weighted_combos(current_combo, counts_left, index):
                    if index == len(combo):
                        yield tuple(current_combo)
                        return
                    ptk = combo[index]
                    max_count = ptk_counter[ptk]
                    for i in range(1, max_count + 1):
                        generate_weighted = current_combo + [ptk] * i
                        yield from generate_weighted_combos(generate_weighted, counts_left, index + 1)

                for real_combo in generate_weighted_combos([], ptk_counter, 0):
                    total = sum(real_combo)
                    for lauta in laudat:
                        min_hukka = lauta * pakollinenhukkaprosentti if pakollinenhukkaprosentti > 0 else 0
                        if (len(real_combo) == 1 and total <= lauta) or (len(real_combo) > 1 and total <= lauta - min_hukka):
                            key = (tuple(sorted(real_combo)), lauta)
                            if key not in yhdistelmat:
                                yhdistelmat[key] = {
                                    "id": f"y{combo_id}",
                                    "combo": real_combo,
                                    "lauta": lauta,
                                    "hukka": lauta - total
                                }
                                combo_id += 1

        prob = LpProblem("Pienin_hukka", LpMinimize)
        combo_vars = {
            v["id"]: LpVariable(v["id"], 0, None, LpInteger)
            for v in yhdistelmat.values()
        }

        prob += lpSum(combo_vars[v["id"]] * v["hukka"] for v in yhdistelmat.values()), "Kokonaishukka"

        ptk_counter = Counter(patkat)
        for ptk in ptk_counter:
            prob += (
                lpSum(combo_vars[v["id"]] * v["combo"].count(ptk) for v in yhdistelmat.values()) == ptk_counter[ptk],
                f"tarve_{ptk}"
            )

        prob.solve(PULP_CBC_CMD(msg=False))

        if LpStatus[prob.status] != "Optimal":
            st.error("❌ Ei löytynyt ratkaisua.")
        else:
            st.success("✅ Optimaalinen ratkaisu löytyi!")
            kokonais_hukka = 0
            kokonais_lautoja = 0
            ratkaisut = []

            for v in yhdistelmat.values():
                count = int(combo_vars[v["id"]].value())
                if count > 0:
                    for _ in range(count):
                        ratkaisut.append((v['lauta'], v['combo'], v['hukka']))
                        kokonais_hukka += v['hukka']
                        kokonais_lautoja += 1

            #st.subheader("📋 Tulokset")
            #for lauta, combo, hukka in ratkaisut:
            #    st.markdown(f"- **Lauta {lauta} mm** | Pätkät: {combo} | Hukka: **{hukka} mm**")
            # Tallenna ratkaisut sessioon

            st.session_state.kokonais_hukka = kokonais_hukka
            st.session_state.kokonais_lautoja = kokonais_lautoja

            total_length = sum([v['lauta'] * int(combo_vars[v['id']].value() or 0) for v in yhdistelmat.values()])
            if total_length > 0:
                hukkapros = round(kokonais_hukka / total_length * 100, 2)
                st.session_state.hukkapros = hukkapros


            # 1) Ratkaisujen taulukko DataFrame
            df_ratkaisut = pd.DataFrame(ratkaisut, columns=["Lauta (mm)", "Pätkät", "Hukka (mm)"])
            # Muotoillaan pätkät pilkuilla erotelluksi tekstiksi
            df_ratkaisut["Pätkät"] = df_ratkaisut["Pätkät"].apply(lambda x: ", ".join(map(str, x)))
            # Järjestestetään taulukko
            df_ratkaisut = df_ratkaisut.sort_values(by="Lauta (mm)").reset_index(drop=True)
            st.session_state.ratkaisut_df = df_ratkaisut

            # 2) Lautojen kappalemäärä
            lauta_counts = df_ratkaisut["Lauta (mm)"].value_counts().reset_index()
            lauta_counts.columns = ["Lauta (mm)", "Kappalemäärä"]
            # Järjestestetään taulukko
            lauta_counts = lauta_counts.sort_values(by="Lauta (mm)").reset_index(drop=True)
            st.session_state.lautamaarat_df = lauta_counts
    except Exception as e:
        st.error(f"⚠️ Virhe laskennassa: {e}")


if "ratkaisut_df" in st.session_state:
    st.subheader("📋 Leikkaustaulukko")
    st.dataframe(st.session_state.ratkaisut_df)

    st.subheader("📋 Lautojen kappalemäärät")
    st.dataframe(st.session_state.lautamaarat_df)

    st.subheader("📊 Yhteenveto")
    st.write(f"🔢 Käytettyjä lautoja: **{st.session_state.kokonais_lautoja}**")
    st.write(f"🗑️ Kokonaishukka: **{st.session_state.kokonais_hukka} mm**")
    st.write(f"📉 Hukkaprosentti: **{st.session_state.hukkapros} %**")

    # Excel-lataus
    excel_buffer = io.BytesIO()
    with pd.ExcelWriter(excel_buffer, engine="xlsxwriter") as writer:
        st.session_state.ratkaisut_df.to_excel(writer, sheet_name="Ratkaisut", index=False)
        st.session_state.lautamaarat_df.to_excel(writer, sheet_name="Lautojen määrä", index=False)
    excel_buffer.seek(0)

    st.download_button(
        label="📥 Lataa kaikki tulokset Excelinä",
        data=excel_buffer,
        file_name="optimoidut_laudat.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
