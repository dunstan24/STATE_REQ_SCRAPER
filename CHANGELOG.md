# Changelog

All notable changes to the Australian Immigration Visa Allocation Scraper will be documented in this file.

## [1.0.0] - 2026-01-26

### Added
- Initial release of Visa Allocation Scraper
- Automated browser scraping with Selenium
- HTML parser fallback method
- Support for Visa Subclass 190 and 491
- State and Territory allocation extraction
- Multiple export formats (Excel, CSV, JSON)
- N8N webhook integration
- Comprehensive logging system
- Data analysis tools
- Summary report generation

### Features
- **Clean Data Extraction**: Filters out monthly invitation data, extracts only state allocations
- **Three Extraction Methods**:
  1. Automated browser scraping
  2. HTML parser (for saved HTML files)
  3. Manual extraction guide
- **Professional Structure**: Organized code in `src/`, documentation in `docs/`
- **Error Handling**: Robust error handling and recovery
- **Configurable**: Easy configuration via `src/config.py`

### Fixed
- ChromeDriver compatibility issues
- Date range extraction bug
- Mixed data from multiple tables (monthly vs state data)
- Proper state-only filtering (ACT, NSW, NT, Qld, SA, Tas, Vic, WA)

### Documentation
- Complete README with quick start guide
- Detailed scraper guide
- Manual extraction guide
- Architecture documentation
- Setup instructions
- Troubleshooting guide

### Target Data
- **Source**: https://immi.homeaffairs.gov.au/visas/working-in-australia/skillselect/invitation-rounds
- **Focus**: State and Territory nominations table
- **Visa Types**: Subclass 190 (Skilled Nominated) and 491 (Skilled Work Regional)
- **States**: ACT, NSW, NT, Qld, SA, Tas, Vic, WA

### Output Format
- Excel files ready for EOI RAW Calculation template
- CSV files for data processing
- JSON files for API integration
- Text summary reports

---

## Future Enhancements

### Planned Features
- [ ] Automatic scheduling support
- [ ] Email notifications on completion
- [ ] Historical data tracking
- [ ] Trend analysis and visualization
- [ ] Database integration
- [ ] REST API endpoint
- [ ] Docker containerization
- [ ] Cloud deployment support

### Under Consideration
- [ ] Support for additional visa subclasses
- [ ] Multi-region support
- [ ] Real-time monitoring
- [ ] Data validation and quality checks
- [ ] Automated testing suite
- [ ] Performance optimization

---

## Version History

| Version | Date | Description |
|---------|------|-------------|
| 1.0.0 | 2026-01-26 | Initial release with full functionality |

---

**Note**: This project follows [Semantic Versioning](https://semver.org/).
