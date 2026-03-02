// 1. Get the data from the previous node
// If coming via Webhook, the data is usually inside 'body' or at the root.
// Try $input.first().json.body if $input.first().json doesn't work.
const data = $input.first().json.body || $input.first().json;

// 2. Define the states (Rows in your sheet)
const states = ['ACT', 'NSW', 'NT', 'Qld', 'SA', 'Tas', 'Vic', 'WA'];

const rows = [];

// 3. Create the list of items for Google Sheets
for (const state of states) {
    rows.push({
        "State Name": state,
        // We map the SCRAPED data to the "Allocated" columns (Column D & F)
        "190 Allocated": data.visa_190?.[state] || 0,
        "491 Allocated": data.visa_491?.[state] || 0,
        "Last Update Scrapped": data.extraction_timestamp || new Date().toISOString()
    });
}

return rows;
