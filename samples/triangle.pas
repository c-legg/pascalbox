program Triangle;

{ Interactive sample:
  Press F5, then type a number into STDIN. }

var
  Rows: Integer;

procedure PrintTriangle(Count: Integer);
var
  Row, Space, Star: Integer;
begin
  for Row := 1 to Count do
  begin
    for Space := 1 to Count - Row do
      Write(' ');
    for Star := 1 to Row * 2 - 1 do
      Write('*');
    WriteLn;
  end;
end;

begin
  Write('How many rows? ');
  ReadLn(Rows);
  PrintTriangle(Rows);
  WriteLn('Done.');
end.
