# URBANopt DiTTo Reader CHANGELOG

# Version 0.5.0
Date Range 04/13/2022 - 11/28/2022
- Fix typo in extended catalog
- Extended catalog updates to match the RNM catalog
- Feature: Add an option to simulate RNM results
- CLI bug fixes

# Version 0.4.0
Date Range: 12/04/2021 - 04/12/2022
- Start and end time not being processes by URBANopt CLI opendss command
- BugFix: Transformer automatic size upgrading doesn't work
- Add export of opendss results in Json format
- Transformer loading factors incorrect in >=v0.3.9
- Custom start/end times don't work on Windows

# Versions 0.3.12 - 0.3.13
Date Range: 11/04/2021 - 12/03/2021
- Addressed a scaling bug in the creation of opendss solar profiles
- moving the requirements to be in setup.py by @tarekelgindy in #25

# Version 0.3.11
Date Range: 09/09/2021 - 11/04/2021
- fix for pypi.org

# Version 0.3.10
Date Range: 04/17/2021 - 09/09/2021
Bug Fixes:

- Raise an error (instead of ignore) when there are discrepancies between the catalog and geojson file.
- Fix a bug regarding a missing upstream_transformer element
- Remove old deleted_element attributes that were in comments and in code causing bugs
- Add checks to set the source voltage based on the high side of the transformers in the system. (assumes transformers are all operating at same nominal voltage).

# Version 0.3.9
Date Range: 03/08/2021 - 04/16/2021

Bugfixes

- Applied unit checking from default feature report (could result in loads being off by factor of 1000)
- Included extra elements in catalog
- Apply phase adjustments when transformers are connected to wrong phase
- Provide option to automatically increase transformer sizes when they're undersized for the peak loads that they serve

# Version 0.3.8
Date Range: 02/23/2021 - 03/08/2021

Allow custom start/end times, and custom timesteps, while defaulting to running the entire simulation period.

# Version 0.3.7
Date: 02/23/2021

- Fix bug handling config file paths

# Versions 0.3.2 - 0.3.6
Date: 02/19/2021

- Change name of package to snake_case
- Move example config file into package
- Add time_points flag to cli
- Make name with dashes explicit
- Update readme to match
- Add update_license cli
- Update copyrights with update_license cli
- Use manifest file to include non-python files in pypi package
- Move electrical_database.json into package
- Add init.py file to reader dir

# Version 0.3.1
Date: 02/18/2021

- Tweaks to clean up pypi appearance

# Version 0.3.0
Date range: 09/08/2020 - 02/18/2021

- Bug fixes & error messages
- Consistency
- Basic CLI
- Rearranged into standard package layout

# Version 0.2.0
Date Range: 4/1/2020 - 9/8/2020

- Updated structure of the URBANopt™ DiTTo Reader package
- Added name and dependencies to setup.py
- Updated urbanopt_example.json to match schema and added default values

# Version 0.1.1
Date: 3/31/2020

# Version 0.1.0
Date: 3/31/2020

- Initial Release of the URBANopt DiTTo Reader