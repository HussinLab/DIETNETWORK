"""Population and continent labels in Diet Network models, along with color palettes for plotting."""

# The diet network outputs are int
# The ints correspond to the following populations in order:
# Ex: ACB = 0, ASW = 1, BEB = 2, CDX = 3, CEUGBR = 4, ...
dn_label_order = [
    'ACB', 'ASW', 'BEB', 'CDX', 'CEUGBR', 'CHB', 'CHS', 'CLM',
    'ESN', 'FIN', 'GIH', 'GWD', 'IBS', 'JPT', 'KHV', 'LWK',
    'MSL', 'MXL', 'PEL', 'PJL', 'PUR', 'STUITU', 'TSI', 'YRI',
]

# Each population belongs to a continent, which is used for continent-level accuracy
# None: for the case where most voted population is None
pop_to_continent = {
    'ACB': 'AFR', 'ASW': 'AFR', 'BEB': 'SAS', 'CDX': 'EAS',
    'CEUGBR': 'EUR', 'CHB': 'EAS', 'CHS': 'EAS', 'CLM': 'AMR',
    'ESN': 'AFR', 'FIN': 'EUR', 'GIH': 'SAS', 'GWD': 'AFR',
    'IBS': 'EUR', 'JPT': 'EAS', 'KHV': 'EAS', 'LWK': 'AFR',
    'MSL': 'AFR', 'MXL': 'AMR', 'PEL': 'AMR', 'PJL': 'SAS',
    'PUR': 'AMR', 'STUITU': 'SAS', 'TSI': 'EUR', 'YRI': 'AFR',
    'None':'None'
}

# Color palette for plotting populations
color_order = [
    'YRI', 'ESN', 'GWD', 'LWK', 'MSL', 'ACB', 'ASW',
    'IBS', 'CEUGBR', 'TSI', 'FIN',
    'PJL', 'BEB', 'GIH', 'STUITU',
    'CHB', 'CHS', 'CDX', 'KHV', 'JPT',
    'MXL', 'CLM', 'PEL', 'PUR', 'None',
]

pop_colors = [
    '#C7E9C0', '#A1D99B', '#74C476', '#41AB5D', '#238B45', '#006D2C', '#00441B',
    '#EFBBFF', '#D896FF', '#BE29EC', '#800080',
    '#FEEDDE', '#FDBE85', '#FD8D3C', '#E6550D',
    '#DEEBF7', '#9ECAE1', '#008080', '#0ABAB5', '#08519C',
    '#BC544B', '#E3242B', '#E0115F', '#900D09', '#808080',
]

pop_palette = dict(zip(color_order, pop_colors))

# Color palette for plotting continents
continent_palette = {
    'AFR': '#238B45',  # Green
    'EUR': '#BE29EC',  # Purple
    'SAS': '#FDBE85',  # Light orange
    'EAS': '#08519C',  # Deep blue
    'AMR': '#E3242B',  # Red
    'None': '#808080',  # Gray
}