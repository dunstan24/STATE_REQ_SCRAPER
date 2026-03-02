// 1. Get the data from the previous node (The Scraper)
const data = $input.first().json; // Depending on your n8n version, might be $input.first().json.data or just $json

// 2. Define the list of states to process
const states = ['ACT', 'NSW', 'NT', 'Qld', 'SA', 'Tas', 'Vic', 'WA'];

const rows = [];

// 3. Loop through each state and create a clean "Row" object
for (const state of states) {
    rows.push({
        "State Name": state,
        "190 Allocation": data.visa_190[state] || 0, // Get the value for this state, or 0 if missing
        "491 Allocation": data.visa_491[state] || 0,
        "Last Update Scrapped": data.extraction_timestamp
    });
}

// 4. Return the 8 separate items
return rows;
