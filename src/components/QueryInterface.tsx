import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Play, Sparkles, Database, Clock, AlertCircle } from "lucide-react";
import { useToast } from "@/hooks/use-toast";

interface DatabaseConfig {
  host: string;
  port: string;
  sid: string;
  username: string;
  password: string;
}

interface SchemaData {
  tables: any[];
  relationships: any[];
}

interface QueryInterfaceProps {
  dbConfig: DatabaseConfig | null;
  schemaData: SchemaData | null;
  onQueryResults: (results: any) => void;
  onNext: () => void;
}

export const QueryInterface = ({ dbConfig, schemaData, onQueryResults, onNext }: QueryInterfaceProps) => {
  const [sqlQuery, setSqlQuery] = useState("");
  const [naturalLanguageQuery, setNaturalLanguageQuery] = useState("");
  const [isExecuting, setIsExecuting] = useState(false);
  const [executionTime, setExecutionTime] = useState<number | null>(null);
  const [queryHistory, setQueryHistory] = useState<string[]>([]);
  const { toast } = useToast();

  const executeQuery = async (query: string, isNaturalLanguage = false) => {
    if (!dbConfig || !schemaData) {
      toast({
        title: "Configuration Missing",
        description: "Please configure database connection and upload schema first",
        variant: "destructive",
      });
      return;
    }

    setIsExecuting(true);
    const startTime = Date.now();

    try {
      // Simulate query execution
      await new Promise(resolve => setTimeout(resolve, 1500));
      
      // Mock results
      const mockResults = {
        columns: ["EMP_ID", "FIRST_NAME", "LAST_NAME", "DEPARTMENT", "SALARY"],
        rows: [
          [1, "John", "Doe", "Engineering", 75000],
          [2, "Jane", "Smith", "Marketing", 65000],
          [3, "Bob", "Johnson", "Engineering", 80000],
          [4, "Alice", "Brown", "HR", 55000],
          [5, "Charlie", "Wilson", "Engineering", 70000]
        ],
        totalRows: 5,
        query: isNaturalLanguage ? `-- Generated from: "${query}"\nSELECT e.emp_id, e.first_name, e.last_name, d.dept_name as department, e.salary\nFROM EMPLOYEES e\nJOIN DEPARTMENTS d ON e.department_id = d.dept_id\nORDER BY e.salary DESC` : query
      };

      const endTime = Date.now();
      setExecutionTime(endTime - startTime);
      
      onQueryResults(mockResults);
      setQueryHistory(prev => [query, ...prev.slice(0, 9)]); // Keep last 10 queries
      
      toast({
        title: "Query Executed Successfully",
        description: `Retrieved ${mockResults.totalRows} rows in ${endTime - startTime}ms`,
      });

      onNext();
    } catch (error) {
      toast({
        title: "Query Failed",
        description: "An error occurred while executing the query",
        variant: "destructive",
      });
    } finally {
      setIsExecuting(false);
    }
  };

  const convertNaturalLanguageToSQL = async () => {
    if (!naturalLanguageQuery.trim()) return;

    setIsExecuting(true);
    try {
      // Simulate OpenAI API call to convert natural language to SQL
      await new Promise(resolve => setTimeout(resolve, 2000));
      
      const generatedSQL = `-- Generated from: "${naturalLanguageQuery}"\nSELECT e.emp_id, e.first_name, e.last_name, d.dept_name as department, e.salary\nFROM EMPLOYEES e\nJOIN DEPARTMENTS d ON e.department_id = d.dept_id\nWHERE e.salary > 60000\nORDER BY e.salary DESC`;
      
      setSqlQuery(generatedSQL);
      
      toast({
        title: "SQL Generated",
        description: "Natural language converted to SQL successfully",
      });
    } catch (error) {
      toast({
        title: "Conversion Failed",
        description: "Failed to convert natural language to SQL",
        variant: "destructive",
      });
    } finally {
      setIsExecuting(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Status Check */}
      {(!dbConfig || !schemaData) && (
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>
            Please complete database connection and schema upload before building queries.
          </AlertDescription>
        </Alert>
      )}

      {/* Query Interface */}
      <Card className="shadow-medium">
        <CardHeader>
          <CardTitle>Query Builder</CardTitle>
          <CardDescription>
            Write SQL queries or use natural language to generate reports
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Tabs defaultValue="natural" className="space-y-4">
            <TabsList className="grid w-full grid-cols-2">
              <TabsTrigger value="natural" className="flex items-center gap-2">
                <Sparkles className="h-4 w-4" />
                Natural Language
              </TabsTrigger>
              <TabsTrigger value="sql" className="flex items-center gap-2">
                <Database className="h-4 w-4" />
                SQL Query
              </TabsTrigger>
            </TabsList>

            <TabsContent value="natural" className="space-y-4">
              <div className="space-y-2">
                <label className="text-sm font-medium">Ask in plain English:</label>
                <Textarea
                  placeholder="e.g., Show me all employees with salary greater than 60000 ordered by salary"
                  value={naturalLanguageQuery}
                  onChange={(e) => setNaturalLanguageQuery(e.target.value)}
                  className="min-h-[100px]"
                />
              </div>
              
              <div className="flex gap-2">
                <Button
                  onClick={convertNaturalLanguageToSQL}
                  disabled={!naturalLanguageQuery.trim() || isExecuting}
                  variant="outline"
                  className="flex items-center gap-2"
                >
                  <Sparkles className="h-4 w-4" />
                  {isExecuting ? "Converting..." : "Convert to SQL"}
                </Button>
                
                <Button
                  onClick={() => executeQuery(naturalLanguageQuery, true)}
                  disabled={!naturalLanguageQuery.trim() || isExecuting}
                  className="bg-gradient-primary flex items-center gap-2"
                >
                  <Play className="h-4 w-4" />
                  Execute Query
                </Button>
              </div>
            </TabsContent>

            <TabsContent value="sql" className="space-y-4">
              <div className="space-y-2">
                <label className="text-sm font-medium">SQL Query:</label>
                <Textarea
                  placeholder="SELECT * FROM EMPLOYEES WHERE..."
                  value={sqlQuery}
                  onChange={(e) => setSqlQuery(e.target.value)}
                  className="min-h-[200px] font-mono text-sm"
                />
              </div>
              
              <Button
                onClick={() => executeQuery(sqlQuery)}
                disabled={!sqlQuery.trim() || isExecuting}
                className="bg-gradient-primary flex items-center gap-2"
              >
                <Play className="h-4 w-4" />
                {isExecuting ? "Executing..." : "Execute Query"}
              </Button>
            </TabsContent>
          </Tabs>
        </CardContent>
      </Card>

      {/* Schema Reference */}
      {schemaData && (
        <Card className="shadow-soft">
          <CardHeader>
            <CardTitle className="text-lg">Available Tables</CardTitle>
            <CardDescription>
              Click on table names to see column details
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {schemaData.tables.map((table, index) => (
                <div key={index} className="border rounded-lg p-3 hover:shadow-soft transition-smooth">
                  <h4 className="font-semibold text-foreground mb-2 flex items-center gap-2">
                    <Database className="h-4 w-4" />
                    {table.name}
                  </h4>
                  <div className="space-y-1">
                    {table.columns.slice(0, 5).map((column: any, colIndex: number) => (
                      <div key={colIndex} className="text-sm text-muted-foreground flex items-center gap-2">
                        <span>{column.name}</span>
                        <Badge variant="outline" className="text-xs">
                          {column.type}
                        </Badge>
                      </div>
                    ))}
                    {table.columns.length > 5 && (
                      <p className="text-xs text-muted-foreground">
                        +{table.columns.length - 5} more columns
                      </p>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Query History */}
      {queryHistory.length > 0 && (
        <Card className="shadow-soft">
          <CardHeader>
            <CardTitle className="text-lg flex items-center gap-2">
              <Clock className="h-5 w-5" />
              Recent Queries
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2 max-h-40 overflow-y-auto">
              {queryHistory.map((query, index) => (
                <div
                  key={index}
                  className="text-sm p-2 bg-muted rounded cursor-pointer hover:bg-muted/80 transition-smooth"
                  onClick={() => {
                    if (query.toLowerCase().includes('select')) {
                      setSqlQuery(query);
                    } else {
                      setNaturalLanguageQuery(query);
                    }
                  }}
                >
                  {query.substring(0, 100)}...
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
};