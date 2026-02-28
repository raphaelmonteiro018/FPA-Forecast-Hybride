# =============================================================================
# ARCHITECTURE : MODÉLISATION HYBRIDE (XGBOOST / HOLT-WINTERS / NAÏVE)
# GESTION DYNAMIQUE DE L'HÉTÉROSCÉDASTICITÉ ET DES RÉGIMES DE VOLATILITÉ
# =============================================================================

import pandas as pd
import numpy as np
import os
import xgboost as xgb
from statsmodels.tsa.holtwinters import ExponentialSmoothing
from pandas.tseries.holiday import USFederalHolidayCalendar

def wape(y_true, y_pred):
    """
    Weighted Average Percentage Error (WAPE) : Métrique de précision 
    prioritaire pour les flux à forte saisonnalité et volumes variables.
    """
    y_true = np.array(y_true)
    y_pred = np.array(y_pred)
    if np.sum(y_true) == 0:
        return 0
    return np.sum(np.abs(y_true - y_pred)) / np.sum(y_true) * 100

# =============================================================================
# 1. INGESTION ET AUDIT STATISTIQUE (ANALYSE P90)
# =============================================================================
file_path = "walmart.xlsm"
sheet_name = "Import retravaillé"
df = pd.read_excel(file_path, sheet_name=sheet_name)

df["ds"] = pd.to_datetime(df["ds"], dayfirst=True)
df["y"] = df["y"].astype(float)

# ANALYSE DE LA VARIANCE : Calcul du ratio Sigma entre Baseline et Pics (Hétéroscédasticité)
df_conso_audit = df.groupby('ds')['y'].sum().reset_index()
p90_threshold = df_conso_audit['y'].quantile(0.90)
std_base = df_conso_audit[df_conso_audit['y'] <= p90_threshold]['y'].std()
std_peak = df_conso_audit[df_conso_audit['y'] > p90_threshold]['y'].std()
hetero_ratio = std_peak / std_base # Coefficient d'ajustement des bornes d'incertitude

stores = df["Store"].unique()
output_dir = "PowerBI_Ready"
os.makedirs(output_dir, exist_ok=True)

df_ca = df.groupby("Store")["y"].sum()
ca_total = df_ca.sum()
all_exports = []
details_audit = []

# =============================================================================
# 2. FEATURE ENGINEERING : CALENDRIER ET SIGNAUX SAISONNIERS
# =============================================================================
start_date = df["ds"].min()
end_date = df["ds"].max() + pd.Timedelta(weeks=12)

cal = USFederalHolidayCalendar()
holidays = cal.holidays(start=start_date, end=end_date)

# Modélisation spécifique du Black Friday (Levier majeur de volume)
black_fridays = []
for year in range(start_date.year, end_date.year + 1):
    thanksgiving = pd.Timestamp(year=year, month=11, day=1) + pd.offsets.Week(weekday=3) + pd.offsets.Week(3)
    black_fridays.append(thanksgiving + pd.Timedelta(days=1))
black_fridays = pd.to_datetime(black_fridays)

def get_weekly_flags(date):
    """Génération de descripteurs binaires pour les périodes de haute activité."""
    week_start = date - pd.Timedelta(days=date.weekday())
    week_end = week_start + pd.Timedelta(days=6)
    has_holiday = ((holidays >= week_start) & (holidays <= week_end)).any()
    has_bf = ((black_fridays >= week_start) & (black_fridays <= week_end)).any()
    week_num = date.isocalendar().week
    month = date.month
    is_peak = 1 if (month == 11 and week_num in [47, 48]) or (month == 12 and week_num in [51, 52]) else 0
    return int(has_holiday or has_bf), is_peak

df[['Holiday_Flag', 'Peak_Week_Flag']] = df['ds'].apply(lambda d: pd.Series(get_weekly_flags(d)))

# Sélection des prédicteurs (Lags auto-régressifs & Composantes exogènes)
FEATURES_ORDER = ["Holiday_Flag", "Peak_Week_Flag", "lag_1", "lag_4", "lag_52", "ma_4", "week_of_year"]

# =============================================================================
# 3. BACKTESTING ET SÉLECTION DU CHAMPION (MODEL TOURNAMENT)
# =============================================================================
FACTEUR_INCERTITUDE = 1.5
HORIZON = 8
HORIZON_TEST = 26

for store_id in stores:
    temp = df[df["Store"] == store_id].sort_values("ds").reset_index(drop=True)
    temp["lag_1"], temp["lag_4"], temp["lag_52"] = temp["y"].shift(1), temp["y"].shift(4), temp["y"].shift(52)
    temp["ma_4"] = temp["y"].rolling(4).mean()
    temp["week_of_year"] = temp["ds"].dt.isocalendar().week.astype(int)

    train_df = temp.dropna().reset_index(drop=True)

    if len(train_df) > 60:
        # Split temporel pour validation hors-échantillon
        train_bench = train_df.iloc[:-HORIZON_TEST].copy()
        test_bench = train_df.iloc[-HORIZON_TEST:].copy()

        # Benchmarking : Modèle Naïf Saisonnier
        preds_naif = temp["y"].shift(52).iloc[test_bench.index]
        score_naif = wape(test_bench["y"], preds_naif)

        # Benchmarking : Holt-Winters (Saisonnalité additive)
        score_hw = 999.0
        try:
            hw_train = temp["y"].iloc[:-HORIZON_TEST]
            hw_test = temp["y"].iloc[-HORIZON_TEST:]
            hw_model = ExponentialSmoothing(hw_train, trend="add", seasonal="add", seasonal_periods=52).fit(optimized=True)
            preds_hw = hw_model.forecast(HORIZON_TEST)
            score_hw = wape(hw_test, preds_hw)
        except: score_hw = 999.0

        # Benchmarking : XGBoost avec Inférence Récursive
        model_xgb = xgb.XGBRegressor(n_estimators=100, learning_rate=0.05, max_depth=5, random_state=42)
        model_xgb.fit(train_bench[FEATURES_ORDER], train_bench["y"])

        preds_rec = []
        hist_rec = train_bench.copy()
        for i in range(HORIZON_TEST):
            nxt_dt = test_bench["ds"].iloc[i]
            h_f, p_f = get_weekly_flags(nxt_dt)
            d_input = pd.DataFrame([{"Holiday_Flag": h_f, "Peak_Week_Flag": p_f, "lag_1": hist_rec["y"].iloc[-1], "lag_4": hist_rec["y"].iloc[-4], "lag_52": hist_rec["y"].iloc[-52], "ma_4": hist_rec["y"].iloc[-4:].mean(), "week_of_year": nxt_dt.isocalendar().week}])
            p_val = model_xgb.predict(d_input[FEATURES_ORDER])[0]
            preds_rec.append(p_val)
            hist_rec = pd.concat([hist_rec, pd.DataFrame({"ds": [nxt_dt], "y": [p_val]})], ignore_index=True)

        score_rec = wape(test_bench["y"], preds_rec)
        
        # Sélection du modèle ayant le WAPE minimal
        scores = {"Naïf": score_naif, "Holt-Winters": score_hw, "XGB_Recursive": score_rec}
        best_model_name = min(scores, key=scores.get)
        best_wape = scores[best_model_name]

        print(f"Magasin {store_id:>2} | Naïf: {score_naif:5.2f}% | HW: {score_hw:5.2f}% | XGB: {score_rec:5.2f}% --> Champion: {best_model_name}")
    else:
        best_model_name, best_wape, score_naif, score_hw, score_rec = "Naïf", 0, 0, 0, 0

    # ENTRAÎNEMENT FINAL SUR L'ENSEMBLE DES DONNÉES DISPONIBLES
    future_dates = pd.date_range(start=temp["ds"].max() + pd.Timedelta(weeks=1), periods=HORIZON, freq="W-FRI")

    if best_model_name == "Holt-Winters":
        final_hw = ExponentialSmoothing(temp["y"], trend="add", seasonal="add", seasonal_periods=52).fit()
        preds_final = final_hw.forecast(HORIZON)
    elif best_model_name == "XGB_Recursive":
        final_xgb = xgb.XGBRegressor(n_estimators=100, learning_rate=0.05, max_depth=5, random_state=42)
        final_xgb.fit(train_df[FEATURES_ORDER], train_df["y"])
        preds_final, hist_final = [], train_df.copy()
        for i in range(HORIZON):
            nxt_dt = future_dates[i]
            h_f, p_f = get_weekly_flags(nxt_dt)
            d_in = pd.DataFrame([{"Holiday_Flag": h_f, "Peak_Week_Flag": p_f, "lag_1": hist_final["y"].iloc[-1], "lag_4": hist_final["y"].iloc[-4], "lag_52": hist_final["y"].iloc[-52], "ma_4": hist_final["y"].iloc[-4:].mean(), "week_of_year": nxt_dt.isocalendar().week}])
            p_v = final_xgb.predict(d_in[FEATURES_ORDER])[0]
            preds_final.append(p_v)
            hist_final = pd.concat([hist_final, pd.DataFrame({"ds": [nxt_dt], "y": [p_v]})], ignore_index=True)
    else:
        preds_final = temp["y"].iloc[-52:-52 + HORIZON].values if len(temp) >= 52 else [temp["y"].mean()] * HORIZON

    details_audit.append({
        "Store": store_id, "Modèle_Gagnant": best_model_name, 
        "WAPE_Naïf": score_naif, "WAPE_HW": score_hw, 
        "WAPE_XGB": score_rec, "WAPE_Champion": best_wape, 
        "Poids": df_ca.loc[store_id] / ca_total
    })

    p_data = pd.DataFrame({"ds": future_dates, "Ventes": preds_final, "Store": store_id, "Type": "Prévision"})
    
    # CALCUL DES BORNES ADAPTATIVES (Gestion du risque par régime de volatilité)
    def calc_adaptive_bounds_with_flag(row):
        _, is_peak = get_weekly_flags(row['ds'])
        local_err = (best_wape / 100) * FACTEUR_INCERTITUDE
        if is_peak:
            local_err *= np.sqrt(hetero_ratio) # On tempère l'effet de l'hétéroscédasticité
        return row['Ventes'] * (1 + local_err), row['Ventes'] * (1 - local_err), int(not is_peak)

    res = p_data.apply(calc_adaptive_bounds_with_flag, axis=1)
    p_data["yhat_upper"], p_data["yhat_lower"], p_data["Flag_Baseline"] = zip(*res)

    h_data = temp[["ds", "y"]].rename(columns={"y": "Ventes"}).assign(Store=store_id, Type="Réel", yhat_upper=np.nan, yhat_lower=np.nan)
    h_data["Flag_Baseline"] = h_data["ds"].apply(lambda d: 1 if get_weekly_flags(d)[1] == 0 else 0)
    
    all_exports.extend([h_data, p_data])

# =============================================================================
# 4. CONSOLIDATION FINALE ET EXPORT BI-READY
# =============================================================================
df_export_final = pd.concat(all_exports, ignore_index=True)
df_audit_results = pd.DataFrame(details_audit)
wape_global = (df_audit_results["WAPE_Champion"] * df_audit_results["Poids"]).sum()
ratio_global = (wape_global / 100) * FACTEUR_INCERTITUDE

df_export_final = df_export_final[["Store", "ds", "Ventes", "yhat_upper", "yhat_lower", "Type", "Flag_Baseline"]]

# Agrégation pour la vue consolidée (Corporate View)
df_conso = df_export_final.groupby(["ds", "Type"]).agg({"Ventes": "sum"}).reset_index()
df_conso["yhat_upper"], df_conso["yhat_lower"] = df_conso["Ventes"], df_conso["Ventes"]
mask_prev = df_conso["Type"] == "Prévision"
df_conso.loc[mask_prev, "yhat_upper"] *= (1 + ratio_global)
df_conso.loc[mask_prev, "yhat_lower"] *= (1 - ratio_global)
df_conso.loc[~mask_prev, ["yhat_upper", "yhat_lower"]] = np.nan
df_conso["Flag_Baseline"] = df_conso["ds"].apply(lambda d: 1 if get_weekly_flags(d)[1] == 0 else 0)

df_synthese = pd.DataFrame([{
    "WAPE_Global_Baseline": wape_global, 
    "Benchmark_Naïf": (df_audit_results['WAPE_Naïf'] * df_audit_results['Poids']).sum(),
    "Benchmark_HW": (df_audit_results['WAPE_HW'] * df_audit_results['Poids']).sum(),
    "Benchmark_XGB": (df_audit_results['WAPE_XGB'] * df_audit_results['Poids']).sum(),
    "Horizon_Test": HORIZON_TEST,
    "Ratio_Hetero": hetero_ratio
}])

filename = f"{output_dir}/Walmart_Forecast_V22_Clean.xlsx"
with pd.ExcelWriter(filename, engine="xlsxwriter") as writer:
    fmt = writer.book.add_format({'num_format': '#,##0.00'})
    df_export_final.to_excel(writer, sheet_name="Histo_Prévisions_Par_Magasins", index=False)
    df_conso.to_excel(writer, sheet_name="Histo_Prévisions_Consolidées", index=False)
    df_audit_results.to_excel(writer, sheet_name="Audit_des_modèles", index=False)
    df_synthese.to_excel(writer, sheet_name="Synthèse_Audit", index=False)
    for s in ["Histo_Prévisions_Par_Magasins", "Histo_Prévisions_Consolidées"]:
        writer.sheets[s].set_column('C:F', None, fmt)

df_base_stats = df_conso_audit[df_conso_audit['y'] <= p90_threshold]
df_peak_stats = df_conso_audit[df_conso_audit['y'] > p90_threshold]
mu_base = df_base_stats['y'].mean()
mu_peak = df_peak_stats['y'].mean()
cv_base = (std_base / mu_base) * 100
cv_peak = (std_peak / mu_peak) * 100

# =============================================================================
# 5. BLOC D'ANALYSE DESCRIPTIVE (CONSOLIDATION FINALE)
# =============================================================================
# Calculs préparatoires
std_base = df_conso_audit[df_conso_audit['y'] <= p90_threshold]['y'].std()
std_peak = df_conso_audit[df_conso_audit['y'] > p90_threshold]['y'].std()
ratio_sigma = std_peak / std_base
coeff_lissage = np.sqrt(ratio_sigma)

wape_champion = (df_audit_results["WAPE_Champion"] * df_audit_results["Poids"]).sum()
marge_baseline = wape_champion * FACTEUR_INCERTITUDE
# La marge Pics conserve le buffer (1.5) et y applique le lissage racine
marge_pics = marge_baseline * coeff_lissage 

print("\n" + "="*95)
print(f"{'Métrique Stratégique':<25} | {'REGIME 1 (Baseline)':<30} | {'REGIME 2 (Pics)':<30}")
print("-" * 95)
print(f"{'Nb. Semaines':<25} | {len(df_base_stats)} (90%){' ':<22} | {len(df_peak_stats)} (10%)")
print(f"{'CA Moyen (μ)':<25} | {mu_base:,.0f} ${' ':<17} | {mu_peak:,.0f} $")
print(f"{'Écart-type (σ)':<25} | {std_base:,.0f} ${' ':<17} | {std_peak:,.0f} $")
print(f"{'Volatilité (CV)':<25} | {cv_base:>6.2f} %{' ':<21} | {cv_peak:>6.2f} %")
print(f"{'Amplitude CA':<25} | [{df_base_stats['y'].min()/1e6:.1f}M$ - {df_base_stats['y'].max()/1e6:.1f}M$]{' ':<10} | [{df_peak_stats['y'].min()/1e6:.1f}M$ - {df_peak_stats['y'].max()/1e6:.1f}M$]")
print("-" * 95)
print(f"{'Erreur Brute (WAPE)':<25} | {wape_champion:>6.2f} % (Champion){' ':<13} | {wape_champion * ratio_sigma:>6.2f} % (Projeté)")
print(f"{'Marge de Sécurité':<25} | {marge_baseline:>6.2f} % (Buffer 1.5x){' ':<10} | {marge_pics:>6.2f} % (Buffer + Lissage)")
print("-" * 95)
print(f"{'Ajustement Risque':<25} | Ratio Sigma Brut : {ratio_sigma:.2f}x | Coeff Lissage (sqrt) : {coeff_lissage:.2f}x")
print("="*95)
