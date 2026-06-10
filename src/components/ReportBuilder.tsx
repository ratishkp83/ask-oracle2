import { useState } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { DatabaseConnection } from "./DatabaseConnection";
import { SchemaUpload } from "./SchemaUpload";
import { QueryInterface } from "./QueryInterface";
import { ResultsDisplay } from "./ResultsDisplay";
import { Database, FileText, Search, BarChart3 } from "lucide-react";

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

export const ReportBuilder = () => {
  const [activeTab, setActiveTab] = useState("connection");
  const [dbConfig, setDbConfig] = useState<DatabaseConfig | null>(null);
  const [schemaData, setSchemaData] = useState<SchemaData | null>(null);
  const [queryResults, setQueryResults] = useState<any>(null);

  return (
    <div className="min-h-screen bg-gradient-secondary">
      <div className="container mx-auto p-6">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-4xl font-bold text-foreground mb-2">
            Smart Report Builder
          </h1>
          <p className="text-muted-foreground text-lg">
            Generate Oracle database reports using SQL or natural language
          </p>
        </div>

        {/* Main Interface */}
        <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-6">
          <TabsList className="grid w-full grid-cols-4">
            <TabsTrigger value="connection" className="flex items-center gap-2">
              <Database className="h-4 w-4" />
              Database
            </TabsTrigger>
            <TabsTrigger value="schema" className="flex items-center gap-2">
              <FileText className="h-4 w-4" />
              Schema
            </TabsTrigger>
            <TabsTrigger value="query" className="flex items-center gap-2">
              <Search className="h-4 w-4" />
              Query
            </TabsTrigger>
            <TabsTrigger value="results" className="flex items-center gap-2">
              <BarChart3 className="h-4 w-4" />
              Results
            </TabsTrigger>
          </TabsList>

          <TabsContent value="connection" className="space-y-4">
            <Card className="shadow-medium">
              <CardHeader>
                <CardTitle>Oracle Database Connection</CardTitle>
                <CardDescription>
                  Configure your Oracle database connection settings
                </CardDescription>
              </CardHeader>
              <CardContent>
                <DatabaseConnection 
                  onConfigSave={setDbConfig}
                  onNext={() => setActiveTab("schema")}
                />
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="schema" className="space-y-4">
            <Card className="shadow-medium">
              <CardHeader>
                <CardTitle>Schema Upload</CardTitle>
                <CardDescription>
                  Upload your table structure and relationship information
                </CardDescription>
              </CardHeader>
              <CardContent>
                <SchemaUpload 
                  onSchemaUpload={setSchemaData}
                  onNext={() => setActiveTab("query")}
                />
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="query" className="space-y-4">
            <QueryInterface 
              dbConfig={dbConfig}
              schemaData={schemaData}
              onQueryResults={setQueryResults}
              onNext={() => setActiveTab("results")}
            />
          </TabsContent>

          <TabsContent value="results" className="space-y-4">
            <ResultsDisplay results={queryResults} />
          </TabsContent>
        </Tabs>
      </div>
    </div>
  );
};