# Copyright 2019 Open End AB
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

rejection_code_english = {
    'MBEV0025': "Payment amount too large.",
    'MTRV0013': "Payee's bank account incorrect.",
    'MTRV0014': "Currency code incorrect or payee's bank cannot process the currency.",
    'MTRV0015': "Non-numeric amount.",
    'MTRV0018': "Zero amount.",
    'MTRV0025': "Deregistered bankgiro number.",
    'MTRV0035': "Bankgiro number lacks payee account.",
    'MTRV0038': "Payee's bank account non-numeric.",
    'MTRV0041': "Payment instruction received too late.",
    'MTRV0042': "Payee's bankgiro number incorrect.",
    'MTRV0043': "Payee's clearing number incorrect.",
    'MTRV0044': "Payee's bankgiro number non-numeric.",
    'MTRV0046': "No bank account for credit transfer.",
    'MTRV0050': "No payee.",
    'MTRV0051': "Credit transfer number incorrect.",
    'MTRV0052': "Incorrect currency for money order.",
    'MTRV0055': "Payment approved, excess information record(s) rejected.",
    'MTRV0056': "Deduction/credit invoice cannot be sent to Swedish Tax Agency bankgiro number.",
    'MTRV0057': "Deduction date incorrect.",
    'MTRV0058': "First monitoring date incorrect.",
    'MTRV0059': "Final monitoring date incorrect.",
    'MTRV0064': "Unreasonable date.",
    'MTRV0081': "Payee's PlusGiro number not found in Bankgirot's directory.",
    'MTRV0082': "Stopped after balance check inquiry. Contact your bank.",
    'MTRV0110': "Payee's name and/or address missing.",
    'MTRV0111': "Payee's PlusGiro number non-numeric.",
    'MTRV0113': "Incorrect PlusGiro payment.",
    'MTRV0124': "Error in OCR number; incorrect length.",
    'MTRV0126': "Credit transfer to bank not connected to Bankgirot.",
    'MTRV0130': "Error in OCR number; incorrect check digit.",
    'MTRV0147': "Incorrect currency for PlusGiro payment.",
    'MTRV0148': "No agreement for specified currency.",
    'MTRV0149': "Remitting bank has no agreement for PlusGiro numbers.",
    'MTRV0152': "Deduction record rejected, last payment date passed.",
    'MTRV0153': "Original amount. Final monitoring date reached.",
    'MTRV0155': "Payment rejected, due to following record.",
    'MTRV0156': "Deduction amount greater than payment or different account numbers/addresses.",
    'MTRV0302': "Mandatory transaction code missing.",
    'MTRV0303': "Records received in incorrect order."
}

rejection_code_swedish = {
    'MBEV0025': 'Betalningen innehåller ett för stort belopp',
    'MTRV0013': 'Mottagarens bankkonto är felaktigt.',
    'MTRV0014': 'Valutakoden är felaktig eller mottagarens bank kan inte hantera valutan',
    'MTRV0015': 'Beloppet är inte numeriskt.',
    'MTRV0018': 'Beloppet är noll',
    'MTRV0025': 'Bankgironumret är avregistrerat.',
    'MTRV0035': 'Bankgironumret saknar mottagarkonto.',
    'MTRV0038': 'Mottagarens bankkonto är inte numeriskt.',
    'MTRV0041': 'Betalningsuppdraget har kommit in för sent.',
    'MTRV0042': 'Mottagarens Bankgironummer är felaktigt.',
    'MTRV0043': 'Mottagarens clearingnummer är felaktigt.',
    'MTRV0044': 'Mottagarens Bankgironummer är inte numeriskt.',
    'MTRV0046': 'Bankkonto saknas för Kontoinsättning.',
    'MTRV0050': 'Mottagare saknas.',
    'MTRV0051': 'Utbetalningsnumret är felaktigt.',
    'MTRV0052': 'Felaktig valuta för Kontantutbetalning.',
    'MTRV0055': 'Betalning godkänd, övertalig(a) informationspost(er) avvisas.',
    'MTRV0056': 'Avdrag/Kreditfaktura går ej att skicka till Bankgironummer som tillhör Skatteverket.',
    'MTRV0057': 'Avdragsdag felaktig.',
    'MTRV0058': 'Första bevakningsdag felaktig.',
    'MTRV0059': 'Sista bevakningsdag felaktig.',
    'MTRV0064': 'Orimligt datum.',
    'MTRV0081': 'Mottagarens pgnr saknas i Bankgirots register.',
    'MTRV0082': 'Stoppad vid Täckningskontroll. Kontakta din bank.',
    'MTRV0110': 'Mottagarens namn och/eller adress saknas.',
    'MTRV0111': 'Mottagarens PGnr är inte numerisk.',
    'MTRV0113': 'Felaktig PlusGirobetalning.',
    'MTRV0124': 'Fel i OCR-numret; felaktig längd.',
    'MTRV0126': 'Kontoinsättning till bank som ej är ansluten till Bankgirot.',
    'MTRV0130': 'Fel i OCR-numret; felaktig Checksiffra.',
    'MTRV0147': 'Felaktig valuta för PlusGirobetalning.',
    'MTRV0148': 'Avtal saknas för angiven valuta.',
    'MTRV0149': 'Avsändande bank saknar avtal för Plusgironummer',
    'MTRV0152': 'Avdragspost avvisad, sista betalningsdag passerad.',
    'MTRV0153': 'Ursprungligt belopp. Sista bevakningsdag är uppnådd.',
    'MTRV0155': 'Betalning avvisad, pga efterkommande Post.',
    'MTRV0156': 'Avdragsbelopp är större än betalning eller olika kontonr/adresser.',
    'MTRV0302': 'Obligatorisk transkod saknas.',
    'MTRV0303': 'Posterna inkom i fel ordning.'
}
