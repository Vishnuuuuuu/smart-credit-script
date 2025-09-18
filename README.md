# SmartCredit Scraper

This project is a Python script that logs into SmartCredit, fetches data, and generates CSV files containing normalized account and credit score data. It uses Playwright for web automation and can handle optional fallback mechanisms.

## Repository

GitHub Repository: [https://github.com/Vishnuuuuuu/smart-credit-script.git](https://github.com/Vishnuuuuuu/smart-credit-script.git)

## Project Structure

```
smartcredit-scraper
├── data
│   ├── smartcredit_accounts.csv
│   ├── smartcredit_scores.csv
│   └── smartcredit_raw.json
├── main.py
├── requirements.txt
├── .env
├── .env.example
└── README.md
```

## Requirements

To run this project, you need to have Python 3.x installed. The required libraries are listed in `requirements.txt`. You can install them using pip:

```bash
pip install -r requirements.txt
```

## Environment Variables

Create a `.env` file in the root directory of the project with the following variables:

```
SMARTCREDIT_EMAIL=your_email@example.com
SMARTCREDIT_PASSWORD=your_password
PLAYWRIGHT_HEADLESS=true  # Set to false if you want to see the browser during execution
```

You can use the provided `.env.example` file as a template.

## Running the Script

To execute the script, run the following command in your terminal:

```bash
python main.py
```

This will log into SmartCredit, fetch the required data, and generate the following files in the `data` directory:

- `smartcredit_accounts.csv`: Contains normalized account data.
- `smartcredit_scores.csv`: Contains normalized credit score data.
- `smartcredit_raw.json`: Stores the raw JSON data fetched from SmartCredit endpoints.

## Optional Playwright Fallback

If you encounter issues with Playwright, ensure that you have the necessary browser binaries installed. You can install them using the following command:

```bash
playwright install
```

If you prefer not to use Playwright, you can modify the script to use an alternative method for data fetching, but this may require additional changes to the code.

## Version and Date of Submission

- Version: 1.0
- Date of Submission: [Insert Date Here]

## License

This project is licensed under the MIT License - see the LICENSE file for details.