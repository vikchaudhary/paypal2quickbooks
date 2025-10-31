# module: paypal2quickbooks.cli
from pathlib import Path
import typer
from paypal2quickbooks.services.converter_service import convert_directory

app = typer.Typer()

@app.command()
def convert(input_dir: Path = Path("."), output_dir: Path = Path("./output")):
    count = convert_directory(input_dir, output_dir)
    typer.echo(f"Converted {count} PDFs to CSVs in {output_dir}")

@app.callback(invoke_without_command=True)
def main(ctx: typer.Context, input_dir: Path = Path("."), output_dir: Path = Path("./output")):
    # Default behavior: run conversion when no subcommand is provided
    if ctx.invoked_subcommand is None:
        count = convert_directory(input_dir, output_dir)
        typer.echo(f"Converted {count} PDFs to CSVs in {output_dir}")

if __name__ == "__main__":
    main()
