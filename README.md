# Smart-Map Plugin (Farm Analytica Fork)

Fork of [SmartMapPlugin](https://github.com/gustavowillam/SmartMapPlugin) maintained by Farm Analytica.

## Original Repository

- **Original Author**: Gustavo Willam
- **Original Repository**: https://github.com/gustavowillam/SmartMapPlugin

## Development

QGIS plugin for smart mapping features.

### Setup

1. Copy directory to QGIS plugin directory
2. Compile resources: `pyrcc5`
3. Run tests: `make test`
4. Enable in QGIS plugin manager

### Customization

- Edit implementation: `Smart_Map.py`
- Modify UI: Open `Smart_Map_Dialog.ui` in Qt Designer
- Replace default icon: `icon.png`
- Compile after changes: `make` (requires GNU make)

## Resources

- [PyQGIS Developer Cookbook](http://www.qgis.org/pyqgis-cookbook/index.html)

(C) 2011-2018 GeoApt LLC - geoapt.com
