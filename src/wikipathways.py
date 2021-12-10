import argparse
import glob
import io
import os
import re
import ssl
import zipfile

import requests
from scour import scour

# # Enable importing local modules when directly calling as script
# if __name__ == "__main__":
#     cur_dir = os.path.join(os.path.dirname(__file__))
#     sys.path.append(cur_dir + "/..")

# from lib import download_gzip

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

# Organisms configured for WikiPathways caching
organisms = [
    "Homo sapiens",
    "Mus musculus"
    # "Danio rerio",
    # "Gallus gallus",
    # "Rattus norvegicus",
    # "Pan troglodytes",
    # "Canis lupus familiaris",
    # "Equus caballus",
    # "Bos taurus",
    # "Caenorhabditis elegans"
]

def get_svg_zip_url(organism):
    date = "20211110"
    base = f"https://wikipathways-data.wmcloud.org/{date}/svg/"
    org_us = organism.replace(" ", "_")
    url = f"{base}wikipathways-{date}-svg-{org_us}.zip"
    return url

class WikiPathwaysCache():

    def __init__(self, output_dir="data/wikipathways/", reuse=False):
        self.output_dir = output_dir
        self.tmp_dir = f"{output_dir}tmp/"
        self.reuse = reuse

        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)
        if not os.path.exists(self.tmp_dir):
            os.makedirs(self.tmp_dir)

    def fetch_svgs(self, organism, org_dir):
        url = get_svg_zip_url(organism)
        print(f"Fetching {url}")

        response = requests.get(url)
        zip = zipfile.ZipFile(io.BytesIO(response.content))
        zip.extractall(org_dir)

        # # with open(output_path, "w") as f:
        # #     f.write(content)
        # with zipfile.ZipFile(output_path, 'r') as zip_ref:
        #     zip_ref.extractall(self.tmp_dir)

        return url

    def optimize_svgs(self, url, org_dir):
        for svg_path in glob.glob(f'{org_dir}*.svg'):
            with open(svg_path, 'r') as f:
                svg = f.read()

            # print('clean_svg')
            # print(clean_svg)
            original_name = svg_path.split("/")[-1]
            name = original_name.split(".svg")[0]
            pwid = re.search(r"WP\d+", name).group() # pathway ID
            optimized_svg_path = self.output_dir + pwid + ".svg"
            print(f"Optimizing to create: {optimized_svg_path}")

            scour_options = scour.sanitizeOptions()
            scour_options.remove_metadata = True
            scour_options.newlines = False
            scour_options.strip_comments = True
            scour_options.strip_ids = True
            scour_options.shorten_ids = True
            scour_options.strip_xml_space_attribute = True
            clean_svg = scour.scourString(svg, options=scour_options)

            repo_url = "https://github.com/eweitz/cachome/tree/main/"
            code_url = f"{repo_url}src/wikipathways.py"
            data_url = f"{repo_url}{optimized_svg_path}"
            wp_url = f"https://www.wikipathways.org/index.php/Pathway:{pwid}"
            provenance = "\n".join([
                "<!--",
                f"  WikiPathways page: {wp_url}",
                f"  URL for this compressed file: {data_url}",
                f"  Uncompressed SVG file: {original_name}",
                f"  From upstream ZIP archive: {url}",
                f"  Source code for compression: {code_url}"
                "-->"
            ])

            clean_svg = clean_svg.replace(
                '<?xml version="1.0" encoding="UTF-8"?>',
                '<?xml version="1.0" encoding="UTF-8"?>\n' + provenance
            )

            clean_svg = re.sub('xml:space="preserve"', '', clean_svg)

            with open(optimized_svg_path, "w") as f:
                f.write(clean_svg)


    def populate_by_org(self, organism):
        """Fill caches for a configured organism
        """
        org_dir = self.tmp_dir + organism.lower().replace(" ", "-") + "/"
        svg_url = self.fetch_svgs(organism, org_dir)
        print('svg_url', svg_url)
        self.optimize_svgs(svg_url, org_dir)

    def populate(self):
        """Fill caches for all configured organisms

        Consider parallelizing this.
        """
        for organism in organisms:
            self.populate_by_org(organism)

# Command-line handler
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--output-dir",
        help=(
            "Directory to put outcome data.  (default: %(default))"
        ),
        default="data/wikipathways/"
    )
    parser.add_argument(
        "--reuse",
        help=(
            "Whether to use previously-downloaded raw SVG zip archives"
        ),
        action="store_true"
    )
    args = parser.parse_args()
    output_dir = args.output_dir
    reuse = args.reuse

    WikiPathwaysCache(output_dir, reuse).populate()
