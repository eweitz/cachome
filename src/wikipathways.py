import argparse
import glob
import io
import os
import re
import ssl
from time import sleep
import zipfile

import requests
from lxml import html, etree
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

def get_pathway_ids_and_names(organism):
    base_url = "https://webservice.wikipathways.org/listPathways"
    params = f"?organism={organism}&format=json"
    url = base_url + params
    response = requests.get(url)
    data = response.json()

    ids_and_names = [[pw['id'], pw['name']] for pw in data['pathways']]
    return ids_and_names

def custom_lossless_optimize_svg(svg):
    """Losslessly decrease size of WikiPathways SVG
    """
    font_family = "\'Liberation Sans\', Arial, sans-serif"
    svg = re.sub(f'font-family="{font_family}"', '', svg)
    style = (
        "<style>" +
            "svg {" +
            f"font-family: {font_family}; "
            "}" +
            # "text {"
            #   "stroke: #000; " +
            #   "fill: #000;" +
            # "}" +
            # "g > a {" +
            #   "color: #000;" +
            # "}" +
        "</style>"
    )
    old_style = '<style type="text/css"></style>'
    svg = re.sub(old_style, style, svg)

    svg = re.sub('xml:space="preserve"', '', svg)

    # Condense colors.
    # Consider using an abstract, general approach instead of hard-coding.
    svg = re.sub('#000000', '#000', svg)
    svg = re.sub('#ff0000', '#f00', svg)
    svg = re.sub('#00ff00', '#0f0', svg)
    svg = re.sub('#0000ff', '#00f', svg)
    svg = re.sub('#00ffff', '#0ff', svg)
    svg = re.sub('#ff00ff', '#f0f', svg)
    svg = re.sub('#ffff00', '#ff0', svg)
    svg = re.sub('#ffffff', '#fff', svg)
    svg = re.sub('#cc0000', '#c00', svg)
    svg = re.sub('#00cc00', '#0c0', svg)
    svg = re.sub('#0000cc', '#00c', svg)
    svg = re.sub('#00cccc', '#0cc', svg)
    svg = re.sub('#cc00cc', '#c0c', svg)
    svg = re.sub('#cccc00', '#cc0', svg)
    svg = re.sub('#cccccc', '#ccc', svg)
    svg = re.sub('#999999', '#999', svg)

    svg = re.sub('#808080', 'grey', svg)

    # Remove "px" from attributes where numbers are assumed to be pixels.
    svg = re.sub(r'width="([0-9.]+)px"', r'width="\1"', svg)
    svg = re.sub(r'height="([0-9.]+)px"', r'height="\1"', svg)
    svg = re.sub(r'stroke-width="([0-9.]+)px"', r'stroke-width="\1"', svg)

    svg = re.sub('fill="inherit"', '', svg)
    svg = re.sub('stroke-width="inherit"', '', svg)
    svg = re.sub('color="inherit"', '', svg)

    svg = re.sub('fill-opacity="0"', '', svg)

    # Match any anchor tag, up until closing angle bracket (>), that includes a
    # color attribute with the value black (#000).
    # For such matches, remove the color attribute but not anything else.
    svg = re.sub(r'<a([^>]*)(color="#000")', r'<a \1', svg)

    svg = re.sub(r'<(rect class="Icon"[^>]*)(color="#000")', r'<rect \1', svg)

    svg = re.sub(r'<(text class="Text"[^>]*)(fill="#000")', r'<\1', svg)
    svg = re.sub(r'<(text class="Text"[^>]*)(stroke="white" stroke-width="0")', r'<\1', svg)

    # svg = re.sub('text-anchor="middle"', '', svg)

    return svg

def custom_lossy_optimize_svg(svg):
    """Lossily decrease size of WikiPathways SVG

    The broad principle is to remove data that does not affect static render,
    but could affect dynamic rendering (e.g. highlighting a specific gene).

    Data removed here could be inferred and/or repopulated in the DOM given a
    schema.  Such a schema would first need to be defined and made available in
    client-side software.  It might make sense to do that in the pvjs library.
    """

    # Remove non-leaf pathway categories.
    svg = re.sub('SingleFreeNode DataNode ', '', svg)
    svg = re.sub('SingleFreeNode Label', 'Label', svg)
    svg = re.sub('Edge Interaction ', '', svg)
    svg = re.sub('Edge Interaction', 'Interaction', svg)

    # Interaction data attributes
    svg = re.sub('SBO_[0-9]+\s*', '', svg)

    # Gene data attributes
    svg = re.sub('Entrez_Gene_[0-9]+\s*', '', svg)
    svg = re.sub('Ensembl_ENS\w+\s*', '', svg)
    svg = re.sub('HGNC_\w+\s*', '', svg)
    svg = re.sub('Wikidata_Q[0-9]+\s*', '', svg)
    svg = re.sub('P594_ENSG[0-9]+\s*', '', svg)
    svg = re.sub('P351_\w+\s*', '', svg)
    svg = re.sub('P353_\w+\s*', '', svg)
    svg = re.sub('P594_ENSG[0-9]+\s*', '', svg)

    # Metabolite data attributes
    svg = re.sub('P683_CHEBI_[0-9]+\s*', '', svg)
    svg = re.sub('P2057_\w+\s*', '', svg)
    svg = re.sub('ChEBI_[0-9]+\s*', '', svg)
    svg = re.sub('ChEBI_CHEBI[0-9]+\s*', '', svg)
    svg = re.sub('P683_[0-9]+', '', svg)
    svg = re.sub('HMDB_\w+\s*', '', svg)

    # Group data attributes
    svg = re.sub('Group GroupGroup', 'GroupGroup', svg)
    svg = re.sub('Group GroupNone', 'GroupNone', svg)
    svg = re.sub('Group Complex GroupComplex', 'GroupComplex', svg)

    svg = re.sub('about="[^"]*"', '', svg)

    svg = re.sub(r'xlink:href="http[^\'" >]*"', '', svg)
    svg = re.sub('target="_blank"', '', svg)

    return svg


class WikiPathwaysCache():

    def __init__(self, output_dir="data/wikipathways/", reuse=False):
        self.output_dir = output_dir
        self.tmp_dir = f"tmp/wikipathways/"
        self.reuse = reuse

        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)
        if not os.path.exists(self.tmp_dir):
            os.makedirs(self.tmp_dir)

    def fetch_svgs(self, ids_and_names, org_dir):

        prev_error_wpids = []
        error_wpids = []

        error_path = org_dir + "error_wpids.csv"
        if os.path.exists(error_path):
            with open(error_path) as f:
                prev_error_wpids = f.read().split(",")
                error_wpids = prev_error_wpids

        for i_n in ids_and_names:
            id = i_n[0]
            svg_path = org_dir + id + ".svg"

            if self.reuse:
                if os.path.exists(svg_path):
                    print(f"Found cache; skip processing {id}")
                    continue
                elif id in prev_error_wpids:
                    print(f"Found previous error; skip processing {id}")
                    continue

            url = f"https://pathway-viewer.toolforge.org/?id={id}"
            # print(url)
            response = requests.get(url)
            if response.ok == False:
                print(f"Response not OK for {url}")
                error_wpids.append(id)
                with open(error_path, "w") as f:
                    f.write(",".join(error_wpids))
                sleep(0.5)
                continue

            content = response.content.decode("utf-8")

            html_path = org_dir + id + ".html"
            # print("Writing " + old_svg_path)
            with open(html_path, "w") as f:
                f.write(content)

            print("Preparing and writing " + svg_path)

            content = content.replace('<?xml version="1.0"?>', "")
            # print("content")
            # print(content)
            tree = etree.fromstring(content)
            # print("tree", tree)
            # svg = etree.tostring(tree.xpath('//svg')[0])
            svg_element = tree.find(".//{http://www.w3.org/2000/svg}svg")
            try:
                svg = etree.tostring(svg_element).decode("utf-8")
            except TypeError as e:
                print(f"Encountered error when stringifying SVG for {id}")
                error_wpids.append(id)
                with open(error_path, "w") as f:
                    f.write(",".join(error_wpids))
                sleep(0.5)
                continue

            svg = '<?xml version="1.0" encoding="UTF-8"?>\n' + svg

            with open(svg_path, "w") as f:
                f.write(svg)
            sleep(1)
        # url = get_svg_zip_url(organism)
        # print(f"Fetching {url}")

        # response = requests.get(url)
        # zip = zipfile.ZipFile(io.BytesIO(response.content))
        # zip.extractall(org_dir)

        # # with open(output_path, "w") as f:
        # #     f.write(content)
        # with zipfile.ZipFile(output_path, 'r') as zip_ref:
        #     zip_ref.extractall(self.tmp_dir)

    def optimize_svgs(self, org_dir):
        for svg_path in glob.glob(f'{org_dir}*.svg'):
            with open(svg_path, 'r') as f:
                svg = f.read()

            svg = re.sub("fill-opacity:inherit;", "", svg)
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

            try:
                clean_svg = scour.scourString(svg, options=scour_options)
            except Exception as e:
                print(f"Encountered error while optimizing SVG for {pwid}")
                continue

            repo_url = "https://github.com/eweitz/cachome/tree/main/"
            code_url = f"{repo_url}src/wikipathways.py"
            data_url = f"{repo_url}{optimized_svg_path}"
            wp_url = f"https://www.wikipathways.org/index.php/Pathway:{pwid}"
            provenance = "\n".join([
                "<!--",
                f"  WikiPathways page: {wp_url}",
                f"  URL for this compressed file: {data_url}",
                # f"  Uncompressed SVG file: {original_name}",
                # f"  From upstream ZIP archive: {url}",
                f"  Source code for compression: {code_url}",
                "-->"
            ])

            clean_svg = clean_svg.replace(
                '<?xml version="1.0" encoding="UTF-8"?>',
                '<?xml version="1.0" encoding="UTF-8"?>\n' + provenance
            )

            # clean_svg = re.sub('tspan x="0" y="0"', 'tspan', clean_svg)
            clean_svg = custom_lossless_optimize_svg(clean_svg)
            clean_svg = custom_lossy_optimize_svg(clean_svg)

            with open(optimized_svg_path, "w") as f:
                f.write(clean_svg)


    def populate_by_org(self, organism):
        """Fill caches for a configured organism
        """
        org_dir = self.tmp_dir + organism.lower().replace(" ", "-") + "/"
        if not os.path.exists(org_dir):
            os.makedirs(org_dir)

        ids_and_names = get_pathway_ids_and_names(organism)
        # ids_and_names = [["WP100", "test"]]
        # print("ids_and_names", ids_and_names)
        self.fetch_svgs(ids_and_names, org_dir)
        self.optimize_svgs(org_dir)

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
