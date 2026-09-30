# Data sources and redistribution policy

This repository distributes **no scientific input data, derived NetCDF files, trained models or
figures**. Users must obtain each product from its official provider and comply with the terms
shown by that provider at download time. Product pages, versions and terms can change; verify
all metadata and redistribution permissions again before a public release or data deposit.

The entries below document the products used by the pipeline. They are not legal advice and do
not grant redistribution rights.

## IASI CO

- **Product:** IASI Level-2 carbon monoxide profiles and integrated columns processed with
  FORLI, using Metop-A and Metop-B for the report period.
- **Processing/version:** the local report archive identifies FORLI products; the exact
  processor version and per-satellite collection identifier must be copied from the downloaded
  file metadata into each run manifest.
- **Official access:** [AERIS IASI portal](https://iasi.aeris-data.fr/) and the
  [Metop-A CO Level-2 product page](https://iasi.aeris-data.fr/co_ac_saf_iasi_a_data/).
- **Method reference:** Hurtmans et al. (2012), *FORLI radiative transfer and retrieval code
  for IASI*, DOI [10.1016/j.jqsrt.2012.02.036](https://doi.org/10.1016/j.jqsrt.2012.02.036).
- **Redistribution:** **not verified**. Do not commit or redistribute source or gridded IASI
  files until the applicable AERIS/EUMETSAT product terms are reviewed for the exact collection.

## MERRA-2

- **Product:** MERRA-2 `inst3_3d_chm_Nv`, three-hourly three-dimensional chemistry fields on
  model levels, including CO and pressure-thickness information used for column integration.
- **Version:** GEOS/MERRA-2 collection version must be read from source metadata and recorded;
  do not infer it solely from a filename.
- **Official access:** [NASA GES DISC MERRA-2 catalogue](https://disc.gsfc.nasa.gov/datasets?project=MERRA-2)
  and [MERRA-2 documentation](https://gmao.gsfc.nasa.gov/reanalysis/MERRA-2/).
- **Core reference:** Gelaro et al. (2017), *The Modern-Era Retrospective Analysis for Research
  and Applications, Version 2 (MERRA-2)*, DOI
  [10.1175/JCLI-D-16-0758.1](https://doi.org/10.1175/JCLI-D-16-0758.1).
- **Redistribution:** **not verified for this collection and derived subset**. Keep all raw and
  derived MERRA-2 files outside Git; confirm NASA/GES DISC terms before any separate deposit.

## CAMS EAC4

- **Product:** CAMS global reanalysis (EAC4), total-column carbon monoxide, eight 3-hourly
  fields per day requested through the Atmosphere Data Store.
- **Dataset DOI:** [10.24381/d58bbf47](https://doi.org/10.24381/d58bbf47).
- **Official access:** [CAMS global reanalysis EAC4](https://ads.atmosphere.copernicus.eu/datasets/cams-global-reanalysis-eac4).
- **Terms:** the catalogue currently presents a Copernicus licence; users must check the
  current attribution and reuse terms when downloading.
- **Redistribution:** **not approved by this repository**. Do not commit downloaded or
  transformed fields. A separate release requires a documented licence review and attribution.

## TROPOMI / Sentinel-5P

- **Product:** S5P-PAL daily Level-3 TROPOMI total-column CO used for 2023-2024 validation.
- **Version:** capture the item identifier, processor version and acquisition timestamps from
  the STAC record in the run manifest; the portal is a living service and version labels must
  not be guessed.
- **Official access:** [S5P-PAL data portal](https://data-portal.s5p-pal.com/) and
  [S5P-PAL API documentation](https://data-portal.s5p-pal.com/apidoc).
- **Instrument reference:** Veefkind et al. (2012), *TROPOMI on the ESA Sentinel-5 Precursor*,
  DOI [10.1016/j.rse.2011.09.027](https://doi.org/10.1016/j.rse.2011.09.027).
- **Redistribution:** **not verified**. Do not commit the global downloads, cropped products or
  derived grids until the precise product terms have been reviewed.

## MOPITT

- **Product:** MOPITT Version 9 Level-2 joint near-infrared and thermal-infrared CO retrieval,
  short name `MOP02J`, version `009`.
- **Official access:** [NASA ASDC MOPITT project](https://asdc.larc.nasa.gov/project/MOPITT),
  [Earthdata Search](https://search.earthdata.nasa.gov/) and the
  [MOPITT product portal](https://www2.acom.ucar.edu/mopitt/products).
- **Account requirement:** downloading MOPITT data requires each user to create and activate
  their own free NASA Earthdata Login account. See
  [the repository setup instructions](docs/earthdata-access.md). Never reuse or share another
  researcher's credentials.
- **Version reference:** Deeter et al. (2021), *Impacts of MOPITT cloud detection revisions on
  observation frequency and mapping of highly polluted scenes*, DOI
  [10.1016/j.rse.2021.112516](https://doi.org/10.1016/j.rse.2021.112516).
- **Redistribution:** **not verified**. NASA Earthdata authentication does not itself grant
  permission to republish files. Keep raw HE5 and cropped NetCDF products outside Git.

## Fire radiative power

- **Product:** monthly, domain-wide FRP classification derived from the fire observations used
  by the original study. The exact upstream product and collection number must be confirmed
  against the source table metadata before release; likely product names must not be substituted
  for evidence.
- **Official background:** [NASA FIRMS](https://firms.modaps.eosdis.nasa.gov/) and the
  [MODIS Active Fire product information](https://www.earthdata.nasa.gov/data/catalog/lpcloud-mod14-061).
- **Redistribution:** **not verified**. The local classification table and any underlying fire
  detections remain outside the repository until provenance and terms are confirmed.

## Climate indices

The `ABCD` feature set may use monthly climate indices in addition to source-field,
spatiotemporal and FRP predictors. Each configured index must carry its provider, variable
definition, temporal aggregation, version or access date, citation and reuse terms in the run
manifest. No local merged index table is redistributed by this repository.

## Required provenance for every external file

For each input, record at least:

- provider and product/collection identifier;
- product and processor version from file metadata;
- acquisition date and original URL or catalogue record;
- original filename, size and SHA-256 checksum;
- spatial/temporal subset and quality filters; and
- applicable citation and terms-of-use URL.
