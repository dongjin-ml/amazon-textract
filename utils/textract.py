import io
import os
import boto3
import logging
from trp import Document
from utils.s3 import s3_handler
from sagemaker.s3 import S3Uploader
from botocore.exceptions import ClientError
from PIL import Image, ImageDraw, ImageFont
from pdf2image import convert_from_path, convert_from_bytes

class textract_handler():
    
    def __init__(self, ):

        # Amazon Textract client
        self.textract = boto3.client('textract')
        self.s3 = s3_handler()
        print (f"This is a Textract handler.")

    def _read_document(self, strDocName, doc_location, bucket_name=None):
        
        # Read document content
        if doc_location == "local":    
            with open(strDocName, 'rb') as document:
                #imageBytes = bytearray(document.read())
                imageBytes = document.read()
            image=Image.open(strDocName)

        elif doc_location == "s3":
            s3_obj = self.s3.get_object(bucket_name=bucket_name, obj_name=strDocName)
            imageBytes = io.BytesIO(s3_obj['Body'].read())
            image=Image.open(imageBytes)
            imageBytes = imageBytes.getbuffer().tobytes()

        return image, imageBytes

    def _ocr_detail(self, blocks, image):

        width, height =image.size  

        # Create image showing bounding box/polygon the detected lines/text
        for block in blocks:
            print('Type: ' + block['BlockType'])
            if block['BlockType'] != 'PAGE':
                print('Detected: ' + block['Text'])
                print('Confidence: ' + "{:.2f}".format(block['Confidence']) + "%")

            print('Id: {}'.format(block['Id']))
            if 'Relationships' in block:
                print('Relationships: {}'.format(block['Relationships']))
            print('Bounding Box: {}'.format(block['Geometry']['BoundingBox']))
            print('Polygon: {}'.format(block['Geometry']['Polygon']))
            print()
            draw=ImageDraw.Draw(image)

            # Draw WORD - Green -  start of word, red - end of word
            if block['BlockType'] == "WORD":
                draw.line([(width * block['Geometry']['Polygon'][0]['X'],
                height * block['Geometry']['Polygon'][0]['Y']),
                (width * block['Geometry']['Polygon'][3]['X'],
                height * block['Geometry']['Polygon'][3]['Y'])],
                fill='green',
                width=2)
            
                draw.line([(width * block['Geometry']['Polygon'][1]['X'],
                height * block['Geometry']['Polygon'][1]['Y']),
                (width * block['Geometry']['Polygon'][2]['X'],
                height * block['Geometry']['Polygon'][2]['Y'])],
                fill='red',
                width=2)    

            # Draw box around entire LINE  
            if block['BlockType'] == "LINE":
                points=[]

                # for polygon in block['Geometry']['Polygon']:
                #     points.append((width * polygon['X'], height * polygon['Y']))
                # draw.polygon((points), outline='black')    

                # Uncomment to draw bounding box
                box=block['Geometry']['BoundingBox']                    
                left = width * box['Left']
                top = height * box['Top']           
                draw.rectangle([left,top, left + (width * box['Width']), top +(height * box['Height'])],outline='black') 

        # Display the image
        image.show()
    
    def detect_text_pdf(self, doc_name, detail=False, bucket_name=None, doc_location="local"):
        
        if doc_location == "local":
            strDocName = doc_name
            images = convert_from_path(strDocName,  fmt="png")
            
        elif doc_location == "s3":
            
            s3_obj_byte_string = self.s3.get_object_client(
                bucket_name=bucket_name,
                obj_name=doc_name
            )

            images = convert_from_bytes(s3_obj_byte_string, fmt="png")

        for idx, imageByte in enumerate(images):
            
            print (f"index: {idx}")
            buffer = io.BytesIO()
            imageByte.save(buffer, 'png')
            buffer = buffer.getvalue()
            
            try:
                response = self.textract.detect_document_text(Document={'Bytes': buffer})
            except ClientError as e:
                logging.error(e)
                print (f"ERROR: {e}")
            
            columns, lines = [], []
            width, height = imageByte.size  
            for idx, item in enumerate(response["Blocks"]):
                
                draw=ImageDraw.Draw(imageByte)            
                if item['BlockType'] == "LINE":
                    #print (f"Index:{idx}, TEXT: '\033[94m' + {item['Text']} + '\033[0m', POS: {item['Geometry']['BoundingBox']}")  
                    box=item['Geometry']['BoundingBox']                    
                    left = width * box['Left']
                    top = height * box['Top']           
                    draw.rectangle([left,top, left + (width * box['Width']), top +(height * box['Height'])],outline='green') 
                    
                    lines.append([idx, item["Text"], item["Geometry"]["BoundingBox"]])


            imageByte.show()            
            lines.sort(key=lambda x: x[0])
            for idx, line in enumerate(lines):
                print (idx, '\033[94m' +  line[1] + '\033[0m', line[2])

            if detail:
                self._ocr_detail(response["Blocks"], imageByte)

        
    def detect_text(self, doc_name, detail=False, bucket_name=None, doc_location="local"):

        if doc_location == "local":
            strDocName = doc_name
            image, imageBytes = self._read_document(strDocName, doc_location=doc_location)
            dicParam = {
                'Bytes': imageBytes
            }
        elif doc_location == "s3":
            strDocName =os.path.join(bucket_name, doc_name)
            image, imageBytes = self._read_document(doc_name, doc_location=doc_location, bucket_name=bucket_name) 
            dicParam = {
                'Bytes': imageBytes
            }

        try:
            response = self.textract.detect_document_text(Document=dicParam)
        except ClientError as e:
            logging.error(e)
            print (f"ERROR: {e}")
            
        if detail:
            self._ocr_detail(response["Blocks"], image)
            
        columns, lines = [], []
        width, height = image.size  
        for idx, item in enumerate(response["Blocks"]):

            draw=ImageDraw.Draw(image)            
            if item['BlockType'] == "LINE":
                #print (f"Index:{idx}, TEXT: '\033[94m' + {item['Text']} + '\033[0m', POS: {item['Geometry']['BoundingBox']}")  
                box=item['Geometry']['BoundingBox']                    
                left = width * box['Left']
                top = height * box['Top']           
                draw.rectangle([left,top, left + (width * box['Width']), top +(height * box['Height'])],outline='green') 

                lines.append([idx, item["Text"], item["Geometry"]["BoundingBox"]])


        image.show()            
        lines.sort(key=lambda x: x[0])
        for idx, line in enumerate(lines):
            print (idx, '\033[94m' +  line[1] + '\033[0m', line[2])
            
            
    def detect_text_table(self, doc_name, bucket_name=None,):
        
        
        s3_obj_byte_string = self.s3.get_object_client(
            bucket_name=bucket_name,
            obj_name=doc_name
        )

        images = convert_from_bytes(s3_obj_byte_string, fmt="png")
        
        for idx, imageByte in enumerate(images):
            
            print (f"index: {idx}")
            buffer = io.BytesIO()
            imageByte.save(buffer, 'png')
            buffer = buffer.getvalue()
            
            try:
                response = self.textract.analyze_document(
                    Document={'Bytes': buffer},
                    FeatureTypes=["TABLES"]
                )
            except ClientError as e:
                logging.error(e)
                print (f"ERROR: {e}")

    #         # Call Amazon Textract
    #         with open(documentName, "rb") as document:
    #             response = textract.analyze_document(
    #                 Document={
    #                     'Bytes': document.read(),
    #                 },
    #                 FeatureTypes=["TABLES"])

    #         #print(response)

            doc = Document(response)

            for page in doc.pages:
                 # Print tables
                for table in page.tables:
                    for r, row in enumerate(table.rows):
                        for c, cell in enumerate(row.cells):
                            print("Table[{}][{}] = {}".format(r, c, cell.text))
