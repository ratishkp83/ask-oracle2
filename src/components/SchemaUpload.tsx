import { useState, useCallback } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Upload, FileText, CheckCircle2, AlertCircle, Table, Link } from "lucide-react";
import { useToast } from "@/hooks/use-toast";

interface SchemaData {
  tables: any[];
  relationships: any[];
}

interface SchemaUploadProps {
  onSchemaUpload: (data: SchemaData) => void;
  onNext: () => void;
}

export const SchemaUpload = ({ onSchemaUpload, onNext }: SchemaUploadProps) => {
  const [uploadedFiles, setUploadedFiles] = useState<{
    schema?: File;
    relationships?: File;
  }>({});
  const [parsedData, setParsedData] = useState<SchemaData | null>(null);
  const [isProcessing, setIsProcessing] = useState(false);
  const { toast } = useToast();

  const handleFileUpload = useCallback((type: 'schema' | 'relationships', file: File) => {
    setUploadedFiles(prev => ({ ...prev, [type]: file }));
    
    // Simulate file parsing
    setIsProcessing(true);
    setTimeout(() => {
      const mockData: SchemaData = {
        tables: [
          {
            name: "EMPLOYEES",
            columns: [
              { name: "EMP_ID", type: "NUMBER", isPrimaryKey: true },
              { name: "FIRST_NAME", type: "VARCHAR2(50)" },
              { name: "LAST_NAME", type: "VARCHAR2(50)" },
              { name: "DEPARTMENT_ID", type: "NUMBER", isForeignKey: true },
              { name: "SALARY", type: "NUMBER" },
              { name: "HIRE_DATE", type: "DATE" }
            ]
          },
          {
            name: "DEPARTMENTS",
            columns: [
              { name: "DEPT_ID", type: "NUMBER", isPrimaryKey: true },
              { name: "DEPT_NAME", type: "VARCHAR2(100)" },
              { name: "MANAGER_ID", type: "NUMBER" },
              { name: "LOCATION", type: "VARCHAR2(100)" }
            ]
          },
          {
            name: "PROJECTS",
            columns: [
              { name: "PROJECT_ID", type: "NUMBER", isPrimaryKey: true },
              { name: "PROJECT_NAME", type: "VARCHAR2(200)" },
              { name: "START_DATE", type: "DATE" },
              { name: "END_DATE", type: "DATE" },
              { name: "BUDGET", type: "NUMBER" }
            ]
          }
        ],
        relationships: [
          {
            from: "EMPLOYEES.DEPARTMENT_ID",
            to: "DEPARTMENTS.DEPT_ID",
            type: "FOREIGN_KEY"
          }
        ]
      };
      
      setParsedData(mockData);
      onSchemaUpload(mockData);
      setIsProcessing(false);
      
      toast({
        title: "Schema Parsed Successfully",
        description: `Found ${mockData.tables.length} tables and ${mockData.relationships.length} relationships`,
      });
    }, 1500);
  }, [onSchemaUpload, toast]);

  const handleDrop = useCallback((e: React.DragEvent, type: 'schema' | 'relationships') => {
    e.preventDefault();
    const files = e.dataTransfer.files;
    if (files.length > 0) {
      handleFileUpload(type, files[0]);
    }
  }, [handleFileUpload]);

  const handleFileInput = useCallback((e: React.ChangeEvent<HTMLInputElement>, type: 'schema' | 'relationships') => {
    const files = e.target.files;
    if (files && files.length > 0) {
      handleFileUpload(type, files[0]);
    }
  }, [handleFileUpload]);

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Schema Structure Upload */}
        <Card className="border-2 border-dashed border-border hover:border-primary/50 transition-smooth">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Table className="h-5 w-5" />
              Table Structure
            </CardTitle>
            <CardDescription>
              Upload CSV/Excel with table names, columns, and data types
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div
              className="border-2 border-dashed border-border rounded-lg p-8 text-center hover:border-primary/50 transition-smooth cursor-pointer"
              onDrop={(e) => handleDrop(e, 'schema')}
              onDragOver={(e) => e.preventDefault()}
              onClick={() => document.getElementById('schema-file')?.click()}
            >
              <Upload className="h-8 w-8 mx-auto mb-4 text-muted-foreground" />
              <p className="text-sm text-muted-foreground mb-2">
                Drop your schema file here or click to browse
              </p>
              <p className="text-xs text-muted-foreground">
                Supports .csv, .xlsx, .xls
              </p>
              <input
                id="schema-file"
                type="file"
                accept=".csv,.xlsx,.xls"
                className="hidden"
                onChange={(e) => handleFileInput(e, 'schema')}
              />
            </div>
            
            {uploadedFiles.schema && (
              <div className="mt-4 flex items-center gap-2 text-sm text-success">
                <FileText className="h-4 w-4" />
                {uploadedFiles.schema.name}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Relationships Upload */}
        <Card className="border-2 border-dashed border-border hover:border-primary/50 transition-smooth">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Link className="h-5 w-5" />
              Table Relationships
            </CardTitle>
            <CardDescription>
              Upload CSV/Excel with foreign key relationships (optional)
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div
              className="border-2 border-dashed border-border rounded-lg p-8 text-center hover:border-primary/50 transition-smooth cursor-pointer"
              onDrop={(e) => handleDrop(e, 'relationships')}
              onDragOver={(e) => e.preventDefault()}
              onClick={() => document.getElementById('relationships-file')?.click()}
            >
              <Upload className="h-8 w-8 mx-auto mb-4 text-muted-foreground" />
              <p className="text-sm text-muted-foreground mb-2">
                Drop your relationships file here or click to browse
              </p>
              <p className="text-xs text-muted-foreground">
                Supports .csv, .xlsx, .xls
              </p>
              <input
                id="relationships-file"
                type="file"
                accept=".csv,.xlsx,.xls"
                className="hidden"
                onChange={(e) => handleFileInput(e, 'relationships')}
              />
            </div>
            
            {uploadedFiles.relationships && (
              <div className="mt-4 flex items-center gap-2 text-sm text-success">
                <FileText className="h-4 w-4" />
                {uploadedFiles.relationships.name}
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {isProcessing && (
        <Alert>
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>
            Processing schema files...
          </AlertDescription>
        </Alert>
      )}

      {parsedData && (
        <Alert className="border-success bg-success/5">
          <CheckCircle2 className="h-4 w-4 text-success" />
          <AlertDescription className="text-success-foreground">
            Schema parsed successfully! Found {parsedData.tables.length} tables and {parsedData.relationships.length} relationships.
          </AlertDescription>
        </Alert>
      )}

      {/* Schema Preview */}
      {parsedData && (
        <Card className="shadow-medium">
          <CardHeader>
            <CardTitle>Schema Preview</CardTitle>
            <CardDescription>
              Review your uploaded schema structure
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {parsedData.tables.map((table, index) => (
                <div key={index} className="border rounded-lg p-4">
                  <h4 className="font-semibold text-foreground mb-2">{table.name}</h4>
                  <div className="grid grid-cols-3 gap-4 text-sm">
                    {table.columns.map((column: any, colIndex: number) => (
                      <div key={colIndex} className="flex items-center gap-2">
                        <span className="font-medium">{column.name}</span>
                        <span className="text-muted-foreground">({column.type})</span>
                        {column.isPrimaryKey && (
                          <span className="text-xs bg-primary text-primary-foreground px-1 rounded">PK</span>
                        )}
                        {column.isForeignKey && (
                          <span className="text-xs bg-accent text-accent-foreground px-1 rounded">FK</span>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      <div className="flex justify-end">
        <Button
          onClick={onNext}
          disabled={!parsedData}
          className="bg-gradient-primary"
        >
          Continue to Query Builder
        </Button>
      </div>
    </div>
  );
};