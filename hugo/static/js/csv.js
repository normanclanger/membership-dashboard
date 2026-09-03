function csvEscape(value) {

    if (value === null || value === undefined) {
        return "";
    }

    const text =
        String(value);

    if (
        text.includes('"') ||
        text.includes(",") ||
        text.includes("\n") ||
        text.includes("\r")
    ) {
        return `"${text.replaceAll('"', '""')}"`;
    }

    return text;
}


export function downloadTableAsCsv(
    table,
    filename,
    options = {}
) {

    if (!table) {
        throw new Error(
            "CSV export table was not found."
        );
    }


    const excludeColumns =
        options.excludeColumns || [];


    const rows =
        Array.from(
            table.querySelectorAll(
                "tr"
            )
        );


    if (!rows.length) {
        throw new Error(
            "There is no data to export."
        );
    }


    const headerCells =
        Array.from(
            rows[0].querySelectorAll(
                "th, td"
            )
        );


    const excludedIndexes =
        new Set();


    headerCells.forEach(
        (cell, index) => {

            const heading =
                cell.textContent
                    .trim();

            if (
                excludeColumns.includes(
                    heading
                )
            ) {
                excludedIndexes.add(
                    index
                );
            }
        }
    );


    const csvRows =
        rows.map(
            row => {

                const cells =
                    Array.from(
                        row.querySelectorAll(
                            "th, td"
                        )
                    );


                return cells
                    .map(
                        (cell, index) => {

                            if (
                                excludedIndexes.has(
                                    index
                                )
                            ) {
                                return null;
                            }

                            const csvValue =
                                cell.dataset.csvValue !== undefined
                                    ? cell.dataset.csvValue
                                    : cell.textContent
                                        .replace(/\s+/g, " ")
                                        .trim();

                            return csvEscape(
                                csvValue
                            );
                        }
                    )
                    .filter(
                        value =>
                            value !== null
                    )
                    .join(",");
            }
        );


    const csv =
        "\uFEFF" +
        csvRows.join("\r\n");


    const blob =
        new Blob(
            [csv],
            {
                type:
                    "text/csv;charset=utf-8;"
            }
        );


    const url =
        URL.createObjectURL(
            blob
        );


    const link =
        document.createElement(
            "a"
        );


    link.href =
        url;

    link.download =
        filename;


    document.body.appendChild(
        link
    );

    link.click();

    document.body.removeChild(
        link
    );


    URL.revokeObjectURL(
        url
    );
}