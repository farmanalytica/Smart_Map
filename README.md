# Smart-Map Plugin (Farm Analytica Fork)

QGIS plugin for spatial interpolation and management-zone generation in precision
agriculture. Provides **Ordinary Kriging**, **Machine Learning interpolation
(Support Vector Machine)**, and **fuzzy management zones**.

Fork of [SmartMapPlugin](https://github.com/gustavowillam/SmartMapPlugin) by
Gustavo Willam, maintained by FARM Analytica.

- **Version**: 1.5.1
- **QGIS minimum**: 3.28
- **License**: see `LICENSE.txt`

---

## Quick Start (Users)

1. Copy this directory into your QGIS plugin folder
   (`<profile>/python/plugins/Smart_Map`).
2. Restart QGIS, enable **Smart-Map** in *Plugins → Manage and Install Plugins*.
3. Launch from the plugin menu/toolbar.

Vendored dependencies (scikit-learn et al.) are provisioned automatically on
first load — no `pip install` needed. See [Dependencies](#dependencies).

---

## Architecture

The plugin follows an **MVC-style layering** with async workers for long-running
math, so the QGIS UI never blocks.

```
┌─────────────┐   user events   ┌──────────────┐   business calls   ┌──────────────┐
│   views/    │ ───────────────▶│ controllers/ │ ──────────────────▶│  managers/   │
│  (PyQt UI)  │◀─────────────── │ (event glue) │◀────────────────── │ (algorithms) │
└─────────────┘   signals/data  └──────────────┘                    └──────┬───────┘
       ▲                              │ dispatch heavy work                │ uses
       │ progress/result signals      ▼                                    ▼
       │                         ┌──────────┐                       ┌─────────────┐
       └─────────────────────────│ workers/ │                       │   krig/     │
                                  │ (QThread)│                       │ (KO math)   │
                                  └──────────┘                       └─────────────┘
```

### Layer responsibilities

| Layer | Dir | Role |
|-------|-----|------|
| **Entry** | `Smart_Map.py`, `__init__.py` | Plugin lifecycle: `classFactory` → `initGui` → `run` → `unload` |
| **Views** | `views/` | PyQt5 dialog + tabbed forms. UI built **programmatically** (no Qt Designer `.ui`) |
| **Controllers** | `controllers/` | Thin event handlers wiring views ↔ managers |
| **Managers** | `managers/` | Business logic / algorithm orchestration |
| **Kriging core** | `krig/` | Pure NumPy/SciPy semivariogram + ordinary-kriging math |
| **Workers** | `workers/` | `QThread` wrappers for non-blocking interpolation/zones |
| **Utils** | `utils/` | Shared helpers (`functions.py`) |
| **i18n** | `i18n/` | pt↔en translations, auto-detected from QGIS locale |
| **Vendored deps** | `extlibs/`, `pysal/`, `skfuzzy/` | Bundled libs provisioned at load |

### Load sequence

1. `__init__.py` → `classFactory(iface)` — provisions `extlibs/` onto `sys.path`,
   returns the `smart_map` instance.
2. `smart_map.__init__` — builds `SmartMapDialog`, sets up the i18n translator.
3. `initGui()` — registers the menu/toolbar action.
4. `run()` — shows the dialog and lazy-initializes controllers wired to views.
5. `unload()` — tears down menu/toolbar actions.

### Controllers

| Controller | File | Controls |
|-----------|------|----------|
| `DataController` | `controllers/data_ctrl.py` | Import CSV/SHP, manage QGIS layers, validate X/Y columns |
| `GridController` | `controllers/grid_ctrl.py` | Build regular interpolation grid from study-area bounds |
| `VariogramController` | `controllers/variogram_ctrl.py` | Fit experimental semivariogram, pick theoretical model |
| `KrigingController` | `controllers/kriging_ctrl.py` | Run OK interpolation, cross-validation, error metrics |
| `SVMController` | `controllers/svm_ctrl.py` | Train SVM (RBF) regressor, run SVM interpolation |
| `ZonesController` | `controllers/zones_ctrl.py` | Fuzzy c-means clustering, optimal-K (FPI/NCE), zone rasters |
| `UIController` | `controllers/ui_ctrl.py` | Tab visibility, multi-step workflow coordination |

### Views

| View | File | Tab |
|------|------|-----|
| `SmartMapDialog` | `views/main_dialog.py` | Main window, 5 tabs |
| `DataView` | `views/data_view.py` | Data import + column picker |
| `VariogramView` | `views/variogram_view.py` | Lag params, model selection, semivariogram plot |
| `KrigingView` | `views/kriging_view.py` | Kriging params, cross-val, OK results |
| `SVMView` | `views/svm_view.py` | SVM C/gamma tuning, results |
| `ZonesView` | `views/zones_view.py` | Fuzzy-K sweep, zone output |
| `styles.py` | `views/styles.py` | Theme/CSS constants |

### Managers

| Manager | File | Algorithms |
|---------|------|-----------|
| `DataManager` | `managers/data_manager.py` | Parse CSV/SHP, validate coords, normalize (StandardScaler) |
| `InterpolationManager` | `managers/interpolation_manager.py` | Fit variogram models, OK/SVM interpolation, cross-val splits |
| `SpatialAnalysisManager` | `managers/spatial_analysis_manager.py` | Moran's I, RFE feature selection |
| `ZonesManager` | `managers/zones_manager.py` | Fuzzy c-means (skfuzzy), FPI/NCE for K selection |
| `ExportManager` | `managers/export_manager.py` | GDAL rasterization, color ramps, QGIS layer registration |

### Kriging core (`krig/`)

| Module | Class / Functions | Role |
|--------|-------------------|------|
| `semivariogram.py` | `Semivariogram` | Experimental γ(h): lag bucketing, pairwise distances (`scipy.spatial`) |
| `variogram_models.py` | `linear_/spherical_/exponential_/gaussian_variogram_model()` | Theoretical models (nugget/range/psill → semivariance) |
| `kriging.py` | `OrdinaryKriging` | Covariance matrix, weights, variance prediction from fitted model |

### Workers (`workers/`)

`QThread` wrappers that run pure compute off the UI thread. The worker emits a
result; the controller's completion slot does all rendering (matplotlib/pyplot,
`setPixmap`, QGIS layer-load **must** stay on the main thread). Wiring is being
rolled out path-by-path.

| Worker | File | Wired? |
|--------|------|--------|
| `InterpolationWorker` | `workers/interpolation_worker.py` | **Kriging cross-validation** and **main interpolation** wired. Batch reuses the same prepare/render path but runs **synchronously** (one variable at a time). SVM still synchronous. |
| `VariogramWorker` | `workers/variogram_worker.py` | **Variogram recompute** wired (single-flight). Interactive handlers (sliders, edits, model combo, adjust, reset) recompute off-thread; batch + saved-param reload stay synchronous. |

Zones interpolation runs synchronously; there is no zones worker (a future slice
would add `zones_manager.calculate_zones` + a worker following the pattern below).

**Pattern** (follow this for new wiring): `build worker(manager, task, **kwargs)
→ connect progress/finished/error → keep a `self._worker` ref (or the QThread is
GC'd) → start() → render in the finished slot`. Per-iteration progress: pass a
`progress_cb` through to the manager loop (see `execute_cross_validation_kriging`).

**Variogram specifics:** the expensive `Semivariogram` (O(n²) pairwise build) is
cached per dataset in `_get_semivariogram` (`Exp_Semiv` was made non-destructive
so it can re-run on the cached object). `calculate_variogram` is the synchronous
compute/apply path; interactive recomputes go through `_recompute_and_plot`, a
**single-flight** worker — at most one runs, the latest request made while busy
is queued, so rapid slider drags never pile up threads or render out of order.

---

## Dependencies

**System-provided by QGIS** (not vendored):

- `numpy` — array math (semivariogram, kriging)
- `scipy` — `spatial.distance`, `optimize.curve_fit` (variogram fitting)
- `pandas` — CSV/DataFrame handling
- `matplotlib` — semivariogram / interpolation / cross-val plots

**Vendored in `extlibs/`** (provisioned onto `sys.path` at plugin load):

- `scikit-learn` 1.5.1 — SVM, RandomForestRegressor, StandardScaler, RFE
- `joblib` 1.4.2, `threadpoolctl` 3.5.0 — sklearn runtime deps

**Bundled in-tree:**

- `skfuzzy/` — fuzzy c-means (management zones)
- `pysal/` — Moran's I

`extlibs_manager.py` detects a Python-version mismatch and re-provisions the
scikit-learn wheels on startup.

---

## Developer Onboarding

### Where to start

- **Add/modify a tab** → edit the matching `views/*_view.py`, wire events in the
  matching `controllers/*_ctrl.py`. UI is pure PyQt — no `.ui` files.
- **Change interpolation math** → `krig/` (kriging) or
  `managers/interpolation_manager.py` (orchestration, cross-validation).
- **New variogram model** → add a function in `krig/variogram_models.py`, then
  register it in `VariogramController` / `VariogramView` model list.
- **Export/raster output** → `managers/export_manager.py`.
- **Heavy compute that freezes UI** → move it into a `workers/` `QThread` and
  surface progress via signals (follow `InterpolationWorker`).

### Conventions

- Keep controllers thin — event glue only; algorithms live in `managers/`/`krig/`.
- Long-running work belongs in a worker thread; never block the QGIS main loop.
- User-facing strings go through `self.tr(...)`. The translation context label is
  `smart_mapDialogBase` (legacy from the old `.ui`); keep it so existing `.qm`
  lookups resolve.

### i18n

```bash
# regenerate the .ts catalog from Python sources
pylupdate5 $(find . -name '*.py') -ts i18n/smart_map_pt_to_en.ts
# compile .ts → .qm
lrelease i18n/smart_map_pt_to_en.ts
```

### Customization quick reference

- Edit lifecycle/wiring: `Smart_Map.py`
- Modify UI: Python views in `views/`
- Replace default icon: `icon.png`

---

## Resources

- [PyQGIS Developer Cookbook](https://docs.qgis.org/latest/en/docs/pyqgis_developer_cookbook/)
- Original project: https://github.com/gustavowillam/SmartMapPlugin
