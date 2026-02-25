import os

app_path = r'C:/Users/DJ/Desktop/acap_rebuild/frontend/app.html'
with open(app_path, 'r', encoding='utf-8', errors='ignore') as f:
    text = f.read()

# 1. Update the Workpaper download buttons
txt_button = '<button class="btn btn-p" style="font-size:10px;" onclick="downloadWpOutput()">⬇ Download .txt</button>'
pdf_word_buttons = '<button class="btn btn-p" style="font-size:10px; margin-right:5px;" onclick="downloadWpDOCX()">⬇ Download Word (.docx)</button>' + '<button class="btn btn-p" style="font-size:10px;" onclick="downloadWpPDF()">⬇ Download PDF</button>'
text = text.replace(txt_button, pdf_word_buttons)

old_btn = '<button class="btn" style="font-size:10px;" onclick="downloadWpText(`\'+text.replace(/`/g,"\'").replace(/\\n/g,\'\\\\n\')+\'`)">⬇ Download</button>'
new_btn = '<button class="btn" style="font-size:10px;" onclick="downloadWpDOCX()">⬇ Download Word</button><button class="btn" style="font-size:10px; margin-left:5px;" onclick="downloadWpPDF()">⬇ PDF</button>'
text = text.replace(old_btn, new_btn)


# 2. Add the actual new JS functions to the bottom of the script block for docx and pdf
# We already have window.docx and window.jspdf from the main script!

js_addon = '''function downloadWpDOCX() {
  var text = document.getElementById('wpOutputPreview').textContent;
  var D = window.docx;
  if(!D) { alert('DOCX library not loaded'); return; }
  
  var paragraphs = text.split('\\n').map(function(line) {
    return new D.Paragraph({
      children: [new D.TextRun({ text: line, font: 'Inter', size: 22 })],
      spacing: { after: 100 }
    });
  });
  
  var doc = new D.Document({
    sections: [{
      properties: {},
      children: paragraphs
    }]
  });
  
  D.Packer.toBlob(doc).then(function(blob) {
    var a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = 'Audit_Workpaper_' + new Date().toISOString().slice(0,10) + '.docx';
    a.click();
  });
}

function downloadWpPDF() {
  var text = document.getElementById('wpOutputPreview').textContent;
  var { jsPDF } = window.jspdf;
  if(!jsPDF) { alert('PDF library not loaded'); return; }
  
  var doc = new jsPDF();
  doc.setFont('helvetica', 'normal');
  doc.setFontSize(10);
  
  var splitText = doc.splitTextToSize(text, 180);
  doc.text(splitText, 15, 20);
  
  doc.save('Audit_Workpaper_' + new Date().toISOString().slice(0,10) + '.pdf');
}
</script>'''

old_fn = '''function downloadWpText(text) {
  var blob = new Blob([text], {type:'text/plain'});
  var a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = 'Workpaper_' + (M3_STATE.org||'Audit').replace(/\\s/g,'_') + '_' + (M3_STATE.period||'').replace(/\\s/g,'_') + '.txt';
  a.click();
}

</script>'''

if old_fn in text:
    text = text.replace(old_fn, js_addon)
else:
    text = text.replace('</script>\n\n\n<!-- ══ ENTERPRISE BOTTOM STRIP ══ -->', js_addon + '\n\n\n<!-- ══ ENTERPRISE BOTTOM STRIP ══ -->')

# 3. Change RACM "Export CSV" to "Export RACM to Excel (.csv)" just to make the UI look correct
text = text.replace('onclick="exportRacmMapping()" id="racmExportBtn" disabled>⬇ Export CSV', 'onclick="exportRacmMapping()" id="racmExportBtn" disabled>⬇ Export Excel (.csv)')


with open(app_path, 'w', encoding='utf-8') as f:
    f.write(text)

print('Updated workpaper formats!')
