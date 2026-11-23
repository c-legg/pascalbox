program HelloPascal;

{ Pascal Box sample
  F5 compiles and runs in a terminal window }

uses
  SysUtils;

var
  I: Integer;
  Total: Integer;

function Square(N: Integer): Integer;
begin
  Result := N * N;
end;

begin
  Total := 0;
  WriteLn('Hello, Pascal!');

  for I := 1 to 5 do
  begin
    Total := Total + Square(I);
    WriteLn('Square(', I, ') = ', Square(I));
  end;

  WriteLn;
  WriteLn('Sum of squares: ', Total);
end.
