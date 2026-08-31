import ExcelJS from "exceljs";

export const SIDEBAR_BLUE = "FF3533cd";
export const LIGHT_GRAY = "FFD3D3D3";

export function pxToWidth(px: number): number {
  return Math.max(8, Math.round(px / 7.5));
}

export const HEADER_STYLE: Partial<ExcelJS.Style> = {
  font: { bold: true, color: { argb: "FFFFFFFF" }, size: 11, name: "Calibri" },
  fill: { type: "pattern", pattern: "solid", fgColor: { argb: SIDEBAR_BLUE } },
  alignment: { vertical: "middle", horizontal: "center", wrapText: true },
  border: {
    top: { style: "thin", color: { argb: SIDEBAR_BLUE } },
    left: { style: "thin", color: { argb: SIDEBAR_BLUE } },
    bottom: { style: "thin", color: { argb: SIDEBAR_BLUE } },
    right: { style: "thin", color: { argb: SIDEBAR_BLUE } },
  },
};

export const DATA_STYLE: Partial<ExcelJS.Style> = {
  font: { size: 10, name: "Calibri" },
  alignment: { vertical: "middle", wrapText: false },
  border: {
    top: { style: "thin", color: { argb: LIGHT_GRAY } },
    left: { style: "thin", color: { argb: LIGHT_GRAY } },
    bottom: { style: "thin", color: { argb: LIGHT_GRAY } },
    right: { style: "thin", color: { argb: LIGHT_GRAY } },
  },
};

export const TITLE_STYLE: Partial<ExcelJS.Style> = {
  font: { bold: true, size: 14, name: "Calibri", color: { argb: SIDEBAR_BLUE } },
  alignment: { vertical: "middle", horizontal: "left" },
};

export function applyHeaderRow(
  sheet: ExcelJS.Worksheet,
  rowNumber: number,
  columns: { header: string }[]
): void {
  const row = sheet.getRow(rowNumber);
  row.height = 22;
  columns.forEach((col, i) => {
    const cell = row.getCell(i + 1);
    cell.value = col.header;
    Object.assign(cell, HEADER_STYLE);
  });
}

export function applyDataRowStyle(row: ExcelJS.Row): void {
  row.eachCell((cell) => {
    Object.assign(cell, DATA_STYLE);
  });
}

export function addTitleRow(
  sheet: ExcelJS.Worksheet,
  title: string,
  columnCount: number
): void {
  const row = sheet.insertRow(1, [title]);
  row.height = 30;
  const cell = row.getCell(1);
  Object.assign(cell, TITLE_STYLE);
  sheet.mergeCells(1, 1, 1, columnCount);
}

export function sendExcel(
  res: import("express").Response,
  workbook: ExcelJS.Workbook,
  filename: string
): void {
  res.setHeader(
    "Content-Type",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
  );
  res.setHeader("Content-Disposition", `attachment; filename="${filename}"`);
  workbook.xlsx.write(res).then(() => res.end());
}
