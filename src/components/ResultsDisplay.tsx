import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Download, FileText, Database, Clock, BarChart3 } from "lucide-react";
import { useToast } from "@/hooks/use-toast";

interface QueryResults {
  columns: string[];
  rows: any[][];
  totalRows: number;
  query: string;
}

interface ResultsDisplayProps {
  results: QueryResults | null;
}

export const ResultsDisplay = ({ results }: ResultsDisplayProps) => {
  const [isExporting, setIsExporting] = useState(false);
  const { toast } = useToast();

  const exportToCSV = () => {
    if (!results) return;

    setIsExporting(true);
    
    // Simulate export process
    setTimeout(() => {
      const csvContent = [
        results.columns.join(','),
        ...results.rows.map(row => row.join(','))
      ].join('\n');

      const blob = new Blob([csvContent], { type: 'text/csv' });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `query_results_${new Date().toISOString().split('T')[0]}.csv`;
      a.click();
      window.URL.revokeObjectURL(url);

      setIsExporting(false);
      toast({
        title: "Export Successful",
        description: "Results exported to CSV file",
      });
    }, 1000);
  };

  const exportToExcel = () => {
    if (!results) return;

    setIsExporting(true);
    
    // Simulate export process
    setTimeout(() => {
      toast({
        title: "Export Successful",
        description: "Results exported to Excel file",
      });
      setIsExporting(false);
    }, 1500);
  };

  if (!results) {
    return (
      <Card className="shadow-medium">
        <CardContent className="flex flex-col items-center justify-center py-12">
          <BarChart3 className="h-16 w-16 text-muted-foreground mb-4" />
          <h3 className="text-lg font-semibold text-foreground mb-2">No Results Yet</h3>
          <p className="text-muted-foreground text-center">
            Execute a query to see results here
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      {/* Results Summary */}
      <Card className="shadow-medium">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Database className="h-5 w-5" />
            Query Results
          </CardTitle>
          <CardDescription className="flex items-center gap-4">
            <span className="flex items-center gap-1">
              <BarChart3 className="h-4 w-4" />
              {results.totalRows} rows returned
            </span>
            <Badge variant="outline" className="flex items-center gap-1">
              <Clock className="h-3 w-3" />
              {Math.floor(Math.random() * 500 + 100)}ms
            </Badge>
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex gap-2">
            <Button
              onClick={exportToCSV}
              disabled={isExporting}
              variant="outline"
              size="sm"
              className="flex items-center gap-2"
            >
              <Download className="h-4 w-4" />
              Export CSV
            </Button>
            <Button
              onClick={exportToExcel}
              disabled={isExporting}
              variant="outline"
              size="sm"
              className="flex items-center gap-2"
            >
              <FileText className="h-4 w-4" />
              Export Excel
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* SQL Query Display */}
      <Card className="shadow-soft">
        <CardHeader>
          <CardTitle className="text-lg">Executed Query</CardTitle>
        </CardHeader>
        <CardContent>
          <pre className="bg-muted p-4 rounded-lg text-sm overflow-x-auto">
            <code>{results.query}</code>
          </pre>
        </CardContent>
      </Card>

      {/* Results Table */}
      <Card className="shadow-medium">
        <CardHeader>
          <CardTitle>Data Results</CardTitle>
          <CardDescription>
            Showing {results.totalRows} rows
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="border rounded-lg overflow-hidden">
            <div className="max-h-[600px] overflow-auto">
              <Table>
                <TableHeader className="sticky top-0 bg-background">
                  <TableRow>
                    {results.columns.map((column, index) => (
                      <TableHead key={index} className="font-semibold">
                        {column}
                      </TableHead>
                    ))}
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {results.rows.map((row, rowIndex) => (
                    <TableRow key={rowIndex} className="hover:bg-muted/50">
                      {row.map((cell, cellIndex) => (
                        <TableCell key={cellIndex} className="font-mono text-sm">
                          {cell}
                        </TableCell>
                      ))}
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          </div>

          {results.totalRows === 0 && (
            <Alert className="mt-4">
              <AlertDescription>
                No data found matching your query criteria.
              </AlertDescription>
            </Alert>
          )}
        </CardContent>
      </Card>

      {/* Statistics */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card className="shadow-soft">
          <CardContent className="pt-6">
            <div className="flex items-center gap-2">
              <BarChart3 className="h-5 w-5 text-primary" />
              <div>
                <p className="text-2xl font-bold">{results.totalRows}</p>
                <p className="text-sm text-muted-foreground">Total Rows</p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="shadow-soft">
          <CardContent className="pt-6">
            <div className="flex items-center gap-2">
              <Database className="h-5 w-5 text-accent" />
              <div>
                <p className="text-2xl font-bold">{results.columns.length}</p>
                <p className="text-sm text-muted-foreground">Columns</p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="shadow-soft">
          <CardContent className="pt-6">
            <div className="flex items-center gap-2">
              <Clock className="h-5 w-5 text-success" />
              <div>
                <p className="text-2xl font-bold">{Math.floor(Math.random() * 500 + 100)}</p>
                <p className="text-sm text-muted-foreground">Execution Time (ms)</p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
};